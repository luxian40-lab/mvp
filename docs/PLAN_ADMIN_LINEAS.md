# PLAN_ADMIN_LINEAS — Las dos líneas desde el admin

Cómo usarlo: «Lee @docs/PLAN_ADMIN_LINEAS.md y ejecuta el paso X siguiendo el protocolo». Las reglas permanentes siguen en `.cursor/rules/eki.mdc`. Encaja en `docs/PLAN_MODULARIDAD_EKI.md` (perfil de línea, fases C y F) y no lo reemplaza.

Escrito el 25 de octubre de 2026. Estado de Meta y del entorno verificado ese día, solo lectura.

## 0. Decisiones

1. La línea principal no se toca: número, WABA, entorno y formulario de campaña quedan como hoy.
2. La línea 2 es el número +57 300 9536193 (6193). Es curso lineal: un curso a la vez, con Formador y Compañero, sin menú, sin planes y sin asesores aparte. Termina el curso, recibe certificado y cierra. El siguiente curso llega con otra campaña.
3. No hay campañas separadas. Es la misma pantalla de Campañas Meta. Al crear una campaña se elige primero la línea (opción B). La línea principal abre el formulario de hoy; la línea 2 abre el mismo formulario en modo «Inicio de curso».
4. En la línea 2 la campaña solo inicia un curso: se elige un curso de los que tenemos y eso es todo. No hay recordatorios por la línea 2.
5. El admin no pide WABA ni phone id. Salen del entorno.
6. El número +57 320 8998063 (8063) no se usa. Lo elimina el dueño de la cuenta en WhatsApp Manager.

## 1. Estado verificado (25 de octubre de 2026)

Empresa Meta «Eki» (`1022655772577644`).

| Phone id | Número | WABA | Estado en Meta | Uso |
|---|---|---|---|---|
| `495439026995771` | +57 301 1859158 | `531283293408942` | Conectado, Cloud API | Línea principal. No se toca. |
| `1272340185973021` | +57 300 9536193 | `1768492384967476` («eki soluciones educativas») | CONNECTED, Cloud API | La línea 2 que se queda. |
| `1435717469615061` | +57 300 9536193 | `1872153990175177` («eki») | PENDING, sin plataforma | Registro duplicado. Es el que tiene hoy el entorno. |
| `894379507087782` | +57 320 8998063 | `1872153990175177` («eki») | CONNECTED, calidad GREEN | Línea 2 antigua (8 de octubre). Se elimina. |

Entorno de producción (`eki-prod-final`):

- `WHATSAPP_PHONE_ID` = `495439026995771`, `WHATSAPP_BUSINESS_ACCOUNT_ID` = `531283293408942`.
- `WHATSAPP_PHONE_NUMBER_ID_2` = `1435717469615061` (el registro pendiente).
- `WHATSAPP_NUMERO_2_E164` = `573009536193`.
- `WHATSAPP_BUSINESS_ACCOUNT_ID_2` no existe.
- `EKI_LINEAS_BD_ENABLED` y `EKI_CURSOS_POR_LINEA` no están (apagados).

Suscripción de la app «eki» (`1082835007966709`) al webhook:

- WABA principal `531283293408942`: suscrita.
- WABA `1768492384967476` (6193 conectada): ninguna app suscrita. Lo que la gente escribe al 6193 no llega a eki.

Plantillas: la WABA principal tiene 10, todas aprobadas. La WABA `1768492384967476` tiene 1 y no aparece aprobada.

Conclusión: hoy la línea 2 no funciona en producción. No es código: es configuración (paso 0).

## 2. Lo que ya existe

- `core/lineas/perfil.py`: perfil de la línea 2 con `curso_directo`, `agentes_en_curso`, `certificado` y `campanas`; sin `menu`, `planes`, `asesores` ni `varios_cursos`.
- `core/lineas/campana.py`: `waba_de_linea`, `plantillas_aprobadas_de_linea` y `plantilla_sirve_en_linea`. Una plantilla no cruza de WABA.
- `core/admin/campana_meta.py`: el formulario ya tiene el campo «Línea» (`phone_number_id`), filtra plantillas por la WABA de la línea y bloquea una plantilla de otra cuenta.
- `core/plantilla_meta_editor.py` (`lineas_disponibles`): arma las opciones del selector. Hoy dice «modo Twilio (curso lineal)» para la línea 2.
- `/admin/lineas/` (`core/views_lineas_admin.py`, `fichas_admin`): pantalla de solo lectura con las dos líneas.
- `core/conversacion/puertas.py` (`abrir_tras_confirmar`) y `core/inicio_curso.py` (`primera_entrega_al_confirmar`): en la línea 2, el sí de los datos entrega saludo y módulo 1 solo si la persona tiene exactamente un curso abierto de esa línea. Con dos abiertos no arranca nada.
- `core/lineas/cursos_linea.py` y `LineaWhatsapp.cursos`: un curso es de una línea porque está en su lista. Sin `EKI_CURSOS_POR_LINEA`, o con la lista vacía, la línea ve todos los cursos.
- `core/campana_audiencia.py`: `poner_en_inicio_de_flujo` deja a la persona al inicio del habeas de esa línea. La variable `curso.nombre` hoy toma el último curso inscrito de la persona.
- `EnvioCampanaMeta` ya tiene el estado `OMITIDO` y `omitido_motivo`.
- `inscribir_estudiante_en_curso` (`core/inscripcion_curso.py`): la misma inscripción que usa el admin de Estudiantes.

## 3. Pasos

| Paso | Qué | Cambia comportamiento | Migración |
|---|---|---|---|
| 0 | Dejar la 6193 conectada | Sí, en la línea 2 (configuración) | No |
| 1 | Nombres claros en el selector | No, solo texto | No |
| 2 | Elegir la línea al crear la campaña | No, con flag | No |
| 3 | Modo «Inicio de curso» en la línea 2 | Sí, con flag, solo línea 2 | Sí, expand |
| 4 | Ver cada línea por separado | No, solo lectura | No |
| 5 | Limpieza de configuración y docs | No | No |

### Paso 0 — Dejar la 6193 conectada [MANUAL, sin código]

En la ventana que decida el usuario. La línea principal no se toca.

1. Verificar, solo lectura:
   - En la base, con qué phone id están los `WhatsappLog`, `SandboxCanalSesion` y `EstadoLinea` del 573009536193. Se espera que no haya filas con `1435717469615061`, porque ese registro está pendiente.
   - Que el token de producción alcance la WABA `1768492384967476`. Leer sus números ya funcionó el 25 de octubre.
2. Suscribir la app «eki» (`1082835007966709`) a la WABA `1768492384967476` (`POST /{waba}/subscribed_apps`, o desde el panel de la app). Mismo webhook que la principal.
3. Entorno, un solo `eb setenv` (reinicia la app unos minutos):
   - `WHATSAPP_PHONE_NUMBER_ID_2=1272340185973021`
   - `WHATSAPP_BUSINESS_ACCOUNT_ID_2=1768492384967476`
4. Crear y aprobar en esa WABA al menos una plantilla de inicio de curso (botón de respuesta rápida, por ejemplo «Iniciar»). Sincronizar Plantillas Meta en el admin.
5. En WhatsApp Manager (lo hace el dueño): eliminar el 8063 y el registro pendiente `1435717469615061` de la WABA `1872153990175177`. El conectado de la 6193 está en otra WABA y no se afecta.

Aceptación: `/admin/lineas/` muestra la línea 2 con la WABA `1768492384967476`; en Campañas Meta, la línea 2 solo ofrece plantillas de esa WABA; con un teléfono interno, escribir al 6193 recibe respuesta por el 6193, y una campaña de prueba recorre habeas, cédula y módulo 1.

Rollback: volver `WHATSAPP_PHONE_NUMBER_ID_2` al valor anterior y quitar `WHATSAPP_BUSINESS_ACCOUNT_ID_2`. La suscripción de la app puede quedarse.

### Paso 1 — Nombres claros en el selector

- `lineas_disponibles`: «Línea principal · menú, planes y asesores» y «Línea 2 · curso lineal». Nada de «modo Twilio».
- Ayudas del formulario de campaña (campo Línea e Inicio de flujo) en el mismo sentido.
- `/admin/lineas/` conserva «Versión Meta» y «Curso lineal» (`core/tests_lineas_admin.py` los exige).

Aceptación: el selector y las ayudas no mencionan Twilio. Ningún envío cambia.

### Paso 2 — Elegir la línea al crear la campaña (opción B)

- «Añadir campaña» abre una página intermedia con la pregunta «¿Por qué línea sale?» y un botón por línea de producto: «Línea principal» y «Línea 2 · Inicio de curso».
- Cada botón abre el formulario de alta con la línea ya puesta (`?linea=<phone_id>`). La línea principal abre el formulario de hoy, sin cambios.
- Una campaña ya creada no cambia de línea: el campo se muestra de solo lectura al editar.
- Flag `EKI_CAMPANA_ELIGE_LINEA`, default `False`. Apagado, «Añadir campaña» abre el formulario de hoy.
- La página intermedia hereda la plantilla de Unfold con barra lateral y Volver (`.cursor/rules/eki-unfold-admin.mdc`).

Aceptación: con el flag apagado, el alta es idéntica a hoy. Con el flag prendido, la línea principal crea la misma campaña que hoy y la línea 2 llega al formulario con la línea fija.

### Paso 3 — Modo «Inicio de curso» en la línea 2

Solo aplica si el perfil de la línea tiene `curso_directo`. La línea principal no pasa por aquí.

Formulario:

- Campo «Curso», obligatorio, con los cursos activos que tenemos.
- «Inicio de flujo» marcado y sin opción de desmarcar.
- Plantillas solo de la WABA de la línea 2 (ya existe).
- Revisión antes de enviar: cuántas personas se inscriben, cuántas ya tenían ese curso y cuántas se omiten por tener otro curso de la línea 2 sin terminar.

Modelo (migración expand, reversible): `CampanaMeta.curso`, `ForeignKey` a `Curso`, `null=True`, `blank=True`, `on_delete=SET_NULL`. Las campañas existentes quedan con `curso` vacío y se comportan como hoy.

Envío, por persona:

- Sin curso abierto de la línea 2: se inscribe en el curso de la campaña (`inscribir_estudiante_en_curso`) y se envía.
- Con ese mismo curso abierto: no se reinscribe; se envía.
- Con otro curso de la línea 2 sin terminar: `OMITIDO`, motivo `otro_curso_abierto`. No se envía.
- La variable `curso.nombre` de la plantilla toma el curso de la campaña, no el último curso inscrito.

Qué cuenta como «curso de la línea 2»: el mecanismo que ya existe, la lista `LineaWhatsapp.cursos` con `EKI_CURSOS_POR_LINEA=true`. Al enviar, la campaña agrega su curso a la lista de la línea 2 si no está. El usuario no la llena a mano. Sin esto, un curso abierto de la línea principal cuenta como segundo curso y `primera_entrega_al_confirmar` no arranca el de la línea 2. La línea principal no tiene lista, así que sigue viendo todos sus cursos como hoy.

Flag `EKI_CAMPANA_INICIO_CURSO`, default `False`. Apagado, una campaña de la línea 2 se envía como hoy.

Aceptación:

- Contrato línea 2 (`core/tests_contrato_linea_2.py`): campaña con curso → habeas → cédula → saludo y módulo 1 del curso de la campaña.
- Persona con un curso abierto de la línea principal recibe la campaña de la línea 2 y arranca el curso de la línea 2.
- Persona con otro curso de la línea 2 sin terminar queda `OMITIDO` con su motivo, y la revisión previa lo cuenta.
- Contrato principal (`core/tests_contrato_linea_principal.py`) sin cambios.

### Paso 4 — Ver cada línea por separado (solo lectura)

- Filtro y columna «Línea» en Campañas Meta (ya existe `nombre_linea`), Estudiantes (por `SandboxCanalSesion` / `EstadoLinea`) y Conversaciones (`WhatsappLog` por línea, migración `0188`).
- Etiqueta en el listado de campañas: «Línea 2 · Inicio de curso: <curso>».
- Tablero por línea en `/admin/lineas/`: campañas enviadas, personas que iniciaron, en curso y terminaron.
- Consultas con ORM; si alguna pesa, índice en migración aparte con `AddIndexConcurrently` y `atomic = False`.

Aceptación: ninguna escritura; mismas cifras que las consultas de verificación del paso 0.

### Paso 5 — Limpieza de configuración y docs

- `ConfiguracionGlobal.cursos_linea_2` ya está oculto en el formulario. Queda sin uso; se quita en un contract posterior, no en el mismo deploy.
- `Cliente.cursos_whatsapp` sigue siendo el catálogo de la empresa en la línea principal. No decide la línea 2.
- `docs/GUIA_PLATAFORMA_1.md` todavía describe el 8063 como segunda línea: actualizar.
- Los tests que usan `894379507087782` como dato de prueba no dependen del número real; se pueden dejar.

## 4. Fuera de este plan

- Pasar las líneas a la base (`EKI_LINEAS_BD_ENABLED`): sirve para líneas nuevas, por ejemplo de clientes. Para estas dos, el entorno basta.
- Botón «Iniciar por línea 2» en cada curso (opción D): atajo posible después del paso 3.
- Cambios en la línea principal.

## 5. Reglas

1. La línea principal es el valor por defecto en todo. Campo vacío, flag apagado o lista vacía = como hoy.
2. Un paso por deploy. Flags nuevos con default `False`. Rollback de los pasos 2 y 3 = apagar su flag.
3. Contratos de las dos líneas en verde en cada commit, más `core/tests_campana_meta.py`, `core/tests_campana_meta_v2.py`, `core/tests_campana_linea.py`, `core/tests_lineas_admin.py`, `core/tests_cursos_linea.py` y `core/tests_perfil_linea.py`.
4. Lógica nueva fuera de `_procesar_twilio_webhook_cuerpo`, `dispatch_sandbox_menu` y `get_response_for_intent`. Lo que cambia por línea se pregunta al perfil, no con `es_modo_twilio()`.
5. No editar un phone id con sesiones guardadas sin revisarlas antes (paso 0.1). No borrar un curso o una línea que esté en una lista.
6. Nada de secretos en git. El token de Meta no se escribe en docs ni en logs.
7. Smoke real con un teléfono interno en cada línea después de cada deploy de los pasos 0, 2 y 3.

## 6. Protocolo

Rama por paso desde `main`. Un cambio por commit. Al cerrar cada paso:

```
PASO: <n>
Commits: <hashes + mensajes>
Archivos tocados / nuevos y estado en git: <lista>
Migraciones nuevas: <lista, reversibles o no>
Resultado: check / makemigrations --check / tests del área
Contratos de línea: principal <ok|n/a>, línea 2 <ok|n/a>
Riesgos o dudas: <lista>
```

Esperar «continúa» antes del siguiente paso. Deploy solo con pedido explícito.

## 7. Terminado

- La 6193 recibe y responde por su propio número, con la WABA `1768492384967476` suscrita a la app.
- Al crear una campaña se elige la línea. La línea principal funciona igual que hoy.
- Una campaña de la línea 2 inicia un solo curso elegido en el formulario, y nadie queda con dos cursos de la línea 2 abiertos.
- El admin muestra campañas, personas y conversaciones por línea.
- El 8063 y el registro pendiente ya no están en WhatsApp Manager.
