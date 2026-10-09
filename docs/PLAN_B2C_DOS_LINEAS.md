# Plan: B2C además de B2B

Estado de hoy en el código. No es un diseño nuevo de tablas. El avance sigue en `ProgresoEstudiante`. El pago B2C ya vive en Studio. La segunda línea de WhatsApp es configuración y enrutado, no un estudiante distinto.

## Cómo se diferencian hoy

| | B2B | B2C |
|---|---|---|
| Señal en base de datos | `Estudiante.cliente` apunta a una organización | `Estudiante.cliente` es `NULL` |
| Curso | `Curso.cliente` = esa organización, o vacío si es general | `Curso.cliente` vacío, `catalogo_menu` y/o `visible_en_studio` |
| Quién inscribe | Coordinador, Excel o campaña de la organización | Studio (pago Wompi) o el menú de Formación en WhatsApp |
| Avance | `ProgresoEstudiante` | El mismo `ProgresoEstudiante` |

`Estudiante.cliente` ya es opcional (`null=True`, `blank=True`). `Curso.cliente` también (`on_delete=SET_NULL`). Un B2C no rompe el esquema B2B.

En el admin de Estudiantes el filtro **Tipo** ya parte la lista: con organización / B2C (sin organización). La línea de totales de arriba usa la misma regla y respeta búsqueda y filtros.

No hace falta un campo `tipo_b2b_b2c` en el estudiante. Si más adelante un alumno B2C entra a una empresa, se le asigna `cliente`. El historial de cursos no se mueve.

## Pedido: no crear otra tabla

El registro de compra B2C ya está en Studio:

- `OrdenStudio`: cuenta, estado (`pendiente` / `aprobado` / `rechazado`), `monto_cop`, `wompi_referencia`, `wompi_transaccion_id`, `pagado_en`.
- `OrdenItemStudio`: curso y precio de cada ítem.
- `AccesoCursoPagado`: el acceso de esa cuenta a ese curso.
- `CuentaAula.estudiante`: une la cuenta web con el `Estudiante` de WhatsApp cuando existen los dos.

Al aprobar el pago, `studio/carrito_service.py` y `studio/pago_service.py` llaman `inscribir_estudiante_en_curso`. Eso crea la fila de `ProgresoEstudiante`. El núcleo de avance no cambia.

`origen_registro` (web Studio vs WhatsApp directo) no está como columna. Hoy se sabe por el camino: orden Wompi = Studio; inscripción sin orden = WhatsApp o admin. Una columna nueva solo cuando haya un tercer origen que no se pueda leer de la orden.

No agregar un modelo `Pedido` paralelo. Duplicaría `OrdenStudio` y partiría el pago en dos sitios.

## Admin (Unfold)

Lo que ya no hay que migrar: cliente opcional en Estudiante y en Curso.

Lo que falta, en este orden:

1. El mismo filtro Tipo en el listado de **Cursos** (con organización / catálogo general). Sin tocar campañas.
2. En la ficha del estudiante, un bloque de solo lectura con las órdenes de su `CuentaAula` (estado, monto, referencia Wompi, cursos). No es un inline editable y no se mezcla con Campañas.
3. Si no hay `CuentaAula`, el bloque dice «Sin compra Studio». No se inventa una orden.

Las campañas B2B siguen filtrando por `cliente`. Un estudiante sin organización no entra en una campaña de empresa salvo que alguien lo asigne.

## Dos números a futuro (B2B y B2C)

Hoy hay una línea Cloud API (`WHATSAPP_PHONE_ID` / `phone_number_id` en la campaña Meta). El número por el que escribe la persona no decide si es B2B o B2C. Lo decide `cliente`.

Cuando exista el segundo número, la regla es esta:

1. Una fila por línea (se puede extender `Linea`, que hoy es Twilio/demo): `phone_number_id`, número visible, rol `b2b` o `b2c`, activa.
2. El webhook lee `metadata.phone_number_id` **antes** de crear o actualizar al estudiante.
3. Línea B2B: el flujo actual (organización, habeas, campaña, plan de la línea). No se le quita el `cliente`.
4. Línea B2C: no se asigna `cliente`. El menú es el catálogo (`catalogo_menu` / Studio). El pago, si lo hay, sigue siendo `OrdenStudio`.
5. La misma cédula puede escribir por las dos líneas. Sigue siendo un `Estudiante`. La línea solo cambia el menú de esa conversación, no duplica la persona.
6. Secretos y umbrales de cada línea (mps, token, ventana de 24 h) salen de settings o de la fila de la línea, no van fijos en el código. Meta primero; Twilio no es el canal nuevo.

Eso no se construye hasta tener el `phone_number_id` del número B2C en Meta. Antes, el código no adivina la línea.

## Cómo empezamos

| Slice | Qué | Qué no |
|---|---|---|
| 0 (hecho) | Filtro Tipo y totales en Estudiantes | — |
| 1 (hecho) | Mismo filtro en Cursos. Bloque de órdenes en la ficha del estudiante | Modelo Pedido nuevo, migración de `cliente` |
| 2 | Revisar que todo pago `aprobado` deje `ProgresoEstudiante` (ya está el camino; falta el test de regresión si no cubre el carrito) | Cambiar Wompi |
| 3 | Tabla de líneas con rol `b2b` / `b2c`, todavía con una sola fila (la línea actual) | Comprar o conectar el segundo número |
| 4 | Webhook enruta por `phone_number_id`. Recién ahí se enchufa el número B2C | Mezclar las dos líneas en una sola campaña |

Cada slice es un commit. El 4 toca webhook: firma HMAC antes de cualquier lógica, y no se despliega sin prueba del número viejo (un mensaje B2B sigue cayendo en la organización de siempre).

## Fuera de este plan

- Subir de máquina o partir Celery (eso es memoria del admin, otro hilo).
- Un portal B2C distinto del aula y de Studio.
- Copiar campañas B2B al número nuevo.
