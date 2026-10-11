# Guía de plataforma eki 1.0

Documento del producto que está en producción el **8 de octubre de 2026**. Meta (WhatsApp Cloud API) es el canal del estudiante. Twilio queda para demos y campañas HSM históricas. Si este texto choca con un párrafo de julio en `docs/GUIA_PLATAFORMA_EKI.md`, manda este archivo.

**Producción:** Elastic Beanstalk `eki-prod-final` (Python 3.11), RDS, S3 `eki-produccion`, Celery y Redis.  
**Deploy vigente:** `linea2-clon-20261008-085700`. Rollback: `eb deploy eki-prod-final --version bienvenida-borrador-20261008-084500`.  
**Repositorio:** monolito Django. El mapa largo de julio sigue en `docs/GUIA_PLATAFORMA_EKI.md`. La deuda de código, en `docs/AUDITORIA_ARQUITECTURA_EKI.md`.

---

## 1. Qué es eki

eki forma personas por WhatsApp y, cuando hace falta, en un aula web. El estudiante avanza con *listo*. La organización ve el programa en el portal. El equipo eki opera en el admin Unfold.

No es una app móvil nativa ni un LMS SCORM. El contenido se escribe una vez (curso, módulo, sección, paso) y sale por WhatsApp y por el aula.

| Quién | Dónde |
|-------|--------|
| Estudiante | Línea Meta, y aula `aprende.eki.technology` si pide *aula* |
| Coordinador de la organización | Portal `app.eki.technology` |
| Equipo eki | Admin `admin.eki.technology` |
| Quien compra en la vitrina | Studio `studio.eki.technology` (aparte del aula) |

---

## 2. Los dos canales de WhatsApp

| Canal | Rol hoy |
|-------|---------|
| **Meta** | Producto. Menú Formación / Asesoría, cursos, agentes, fichas. El proveedor del menú es `SANDBOX_PROVEEDOR=meta`. |
| **Twilio** | Demo y campañas HSM históricas. No acumula las rachas de la línea Meta. |

El webhook es uno (`whatsapp_webhook`): JSON de Meta o formulario de Twilio. La firma se valida antes de la lógica. Meta usa HMAC-SHA256 del cuerpo crudo; Twilio usa `RequestValidator`. La comparación es `hmac.compare_digest`.

Con el menú en Meta, un mensaje de Twilio dirigido al número de esa línea se acepta con HTTP 200 y **no se responde**. El código está en `_aplicar_sandbox_menu` (`sandbox_twilio_inbound_ignorado`). Las campañas y el flujo educativo de Twilio siguen en el webhook cuando el destino no es esa línea.

Hay dos números en la misma app. Comparten menú, planes, cursos, agentes y cupo (el cupo es de la persona, no de la línea). La respuesta sale por el número al que escribieron (`metadata.phone_number_id`), no siempre por el id de settings.

| Línea | Variable del id | Número |
|-------|-----------------|--------|
| Principal | `WHATSAPP_PHONE_ID` | la que ya estaba en producción |
| Segunda | `WHATSAPP_PHONE_NUMBER_ID_2` y `WHATSAPP_NUMERO_2_E164` | +57 320 8998063, id `894379507087782` |

El 8 de octubre de 2026 Meta reportó esa segunda línea CONNECTED, nombre aprobado (Eki), calidad GREEN y plataforma Cloud API. El código de registro figura EXPIRED; no se re-registró porque ya está conectada. El mismo día quedaron en el entorno `WHATSAPP_PHONE_NUMBER_ID_2` y `WHATSAPP_NUMERO_2_E164`, junto con el deploy `linea2-clon-20261008-085700`. Quien escribe al 8063 recibe el mismo menú, planes, cursos y agentes, y la respuesta sale por ese número. Quien escribe a la línea principal sigue recibiendo la respuesta por la principal.

Hay dos cuentas de WhatsApp, las dos se llaman «eki» y las dos cuelgan del negocio Eki (`1022655772577644`). El 8 de octubre por la tarde el servidor pasó a usar solo la del 9158: `WHATSAPP_BUSINESS_ACCOUNT_ID=531283293408942`. El 8063 y el 6193 siguen en la otra cuenta (`1872153990175177`), pero quedaron en pausa en eki: se vaciaron `WHATSAPP_PHONE_NUMBER_ID_2` y `WHATSAPP_NUMERO_2_E164`. Una plantilla no cruza de cuenta. Las de bienvenida aprobadas en la cuenta del 8063 no sirven para el 9158; hay que pedirlas otra vez ahí. El id `102265577257764` que se había guardado antes era el negocio, sin el último 4, no una cuenta de WhatsApp.

Un POST de Twilio hacia cualquiera de las dos e164 se ignora igual que antes.

El plan por defecto de quien no tiene uno en Meta es `LINEA_META_PLAN_DEFAULT=curso_asesor` (OP1). En Twilio demo, `LINEA_DEMO_TWILIO_PLAN`, también OP1 si no se cambia.

---

## 3. Planes de la línea Meta

El plan vive en la organización (`Cliente.plan_linea_meta`) y se puede pisar por grupo (`GrupoEstudiantes.plan_linea_meta`). Un override por persona en Admin → Sesiones menú sandbox gana sobre el grupo. Una suscripción vencida apaga también el plan del grupo.

| Plan | Qué abre | Cursos nuevos en el mes | Preguntas al asesor en el mes |
|------|----------|-------------------------|-------------------------------|
| **OP1** `curso_asesor` | Formación y Asesoría | 1 | 30 |
| **OP2** `cursos` | Solo Formación | 2 | 0 |
| **OP3** `asesor` | Solo Asesoría | 0 | 60 |

Un curso ya abierto este mes entra directo («Seguimos *nombre*»). Dos o más preguntan cuál. Cero muestra el menú y el carrusel de Formación.

El carrusel sale de cursos activos con **En el menú de Formación**, sin cliente dueño. WhatsApp pide de 2 a 10 tarjetas; si hay más, se parte en varios carruseles.

*listo* entrega el módulo completo en ese turno. Un segundo *listo* mientras el primero va en camino no manda otra copia. La espera es una reacción ⏳ en el mensaje de la persona y ✅ cuando sale la respuesta. La racha va dentro del primer mensaje del día.

---

## 4. Asesoría: cinco oficios

La lista no usa nombres propios. Cada agente recuerda su conversación. *reiniciar* corta esa memoria. *menu* vuelve al menú.

| Lista | Oficio | Qué responde | Qué no responde |
|-------|--------|--------------|-----------------|
| Agrónomo eki | Cultivo, plagas y suelo | El lote de hoy | Precios ni hábitos |
| Coach eki | Hábitos y constancia | El primer paso | Cultivo ni precios |
| Profesor IA | IA en el celular | Nota de voz, mensaje a un comprador, lista simple | Plagas ni ventas |
| Ventas eki | Clientes, precio y cierre | A quién le vende | Plagas ni hábitos |
| Experto en finanzas | Gastos, deudas y cuentas | El gasto o la deuda de hoy | Plagas ni cómo conseguir clientes |

El trato es de usted, corto, una pregunta al cierre. El chat usa `BOT_COMERCIAL_OPENAI_MODEL` (default `gpt-5-mini`). La pregunta técnica del agrónomo puede subir a `BOT_COMERCIAL_MODEL_TECNICO` (`gpt-5`). Si el modelo falla, hay un segundo intento y, si tampoco hay texto, una respuesta del mismo oficio. El agrónomo de la línea Meta no se presenta como Nat.

Fuentes de cada oficio:

| Oficio | De dónde sale lo que dice |
|--------|---------------------------|
| Agrónomo eki | Agrosavia, en el camino del agrónomo (`core/agrosavia_connector.py`, llamado desde el bot comercial cuando el menú enruta a Nat). |
| Ventas eki | FAO, repositorio público `openknowledge.fao.org` (`core/fao_connector.py`). Solo si la pregunta es comercial (precio, clientes, margen, cooperativa). Se apaga con `BOT_VENTAS_FAO_ENABLED=false`. El 8 de octubre de 2026 el archivo exigía User-Agent de navegador; sin eso responde 403. Aún no está en el deploy de producción. |
| Coach, Profesor IA, Finanzas | Conocimiento aprobado en admin (`ConocimientoAgente`). No tienen conector externo. |

La medición de impacto por preguntas dentro de la conversación (línea base, seguimiento y cierre, sin gastar cupo) está especificada y **no está implementada**. Lo que sí existe es la captura de indicadores que el agente anota cuando la persona responde en el chat (`core/impacto_captura.py`), distinta de esa encuesta.

El bot comercial de una organización (su propio número) sigue aparte: entra por `numero_whatsapp_nat`.

---

## 5. Quién puede usar la línea

En el deploy vigente el menú pide habeas antes de abrir formación o asesoría: *Acepto* o *No acepto*. Sin eso no entra al menú. La ficha puede seguir en `ESPERANDO_HABEAS_DATA` desde un flujo anterior.

Quien escribe por Meta y nadie le cambia el nombre queda como **Usuario**. El nombre de perfil de WhatsApp no se guarda. Por eso buscar «Andreina» o «Igualluisa» no encuentra un mensaje que sí entró con otro nombre.

En la rama de trabajo hay además un corte (`LINEA_META_SOLO_REGISTRADOS`) para números sin organización, progreso ni grupo. **Eso no está en el deploy del 5 de octubre.** No explica el silencio de estas dos fichas en producción.

---

## 6. Portal, aula, Studio, admin

| Superficie | Host | Qué hay |
|------------|------|---------|
| Portal | `app.eki.technology` | Coordinación de la organización. El inicio ya no muestra «¿Cómo va mi programa?» ni la tarjeta de Métricas / Centro de Éxito. Siguen cursos, herramientas y el mapa. Centro de Éxito, suscripción, certificados y productos opcionales (GEI, Nat, empleabilidad) siguen en sus pantallas. |
| Aula | `aprende.eki.technology` | Estudio, tareas, biblioteca, perfil, ranking. Entra con *aula* por WhatsApp. |
| Studio | `studio.eki.technology` | Catálogo, inscripción, checkout Wompi y handoff firmado al aula. No es el portal. |
| Certificados | `certificados.eki.technology` | Verificación pública, PDF y hash. WhatsApp sigue enviando el PNG. |
| Admin | `admin.eki.technology` | Unfold: Inicio, analítica, Copiloto ops, campañas, Module Builder, Course Engine, Knowledge Studio. Tonos Cielo, Marca y Oscuro. |

Identidad visual del portal, Studio y Aprende: `#9A6CAC`, `#7A4E8E`, `#5F3A6E`.

---

## 7. Plantillas de Meta

Una plantilla se crea en la cuenta de WhatsApp Business (WABA) con `WHATSAPP_BUSINESS_ACCOUNT_ID` y `WHATSAPP_TOKEN`. El alta queda en revisión. Solo se puede enviar cuando el estado es **APPROVED**. Un HTTP 200 de Graph es «aceptado», no «entregado». El fallo llega después por el webhook de estados (`131026` no entregable, `131047` fuera de la ventana de 24 h, `131048` calidad del remitente, `131049` límite del ecosistema).

Desde el 8 de octubre de 2026 por la tarde `WHATSAPP_BUSINESS_ACCOUNT_ID` en producción es `531283293408942`, la cuenta del 9158. `WHATSAPP_APP_ID` sigue vacío: el carrusel con foto no se puede publicar.

Ese mismo día, por la tarde, Meta aprobó los cuatro textos en la cuenta del 9158: `eki_bienvenida_texto`, `eki_bienvenida_curso`, `eki_bienvenida_generica` y `eki_bienvenida_asesoria`. La prueba de «Prueba audiencia habeas» salió por el 9158 con `eki_bienvenida_curso`. Las fichas son Luisa Salazar (teléfono terminado en 7958), Andreina Diaz (4345) y la del 0629, que en la ficha se llama Julian. Meta aceptó el envío a las tres. El carrusel sigue en borrador. El botón *No recibir más* todavía no está en la lista de baja (`es_optout`).

El id anterior `102265577257764` no era una cuenta que el token pudiera leer. Graph respondía que el objeto no existe.

---

## 8. Qué no llegó de Andreina Diaz ni de Igualluisa Salazar

Las dos escribieron, según el equipo, a la línea de Meta. En producción, el 6 de octubre, esas fichas no tienen ninguna fila con canal Meta, ni comparando los últimos dígitos del teléfono. La línea sí está viva: en 14 días hay 36 entradas con id de Meta, 8 marcadas canal Meta y 28 salidas Meta. No hay webhooks de Meta fallidos en ese periodo. Las credenciales de Twilio siguen cargadas; el menú de producto está en Meta.

- **Andreina Diaz** (ficha 1915) está activa y en espera de habeas. Su historial (último mensaje de ella el 15 de mayo de 2026, respuesta entregada segundos después) no tiene canal Meta. La ficha es del canal anterior.
- **Igualluisa Salazar** no está como nombre ni dentro del texto de los mensajes. Hay dos fichas con apellido Salazar (2108 y 1603), también sin canal Meta. La 2108 no tiene mensajes. La 1603 tiene tres salidas antiguas, la última el 29 de julio de 2026.

En los 14 días previos al 6 de octubre hubo entradas en la línea y, en esos hilos, una salida después. El silencio no es de toda la línea.

Causas que cuadran con el código que está en producción, de la más cercana a la más lejana:

1. **El teléfono de la ficha no es el que escribió.** La salida de Meta se guarda con el número que llega en el webhook. Si no coincide con la ficha, esa ficha queda en cero mensajes de Meta aunque la línea sí haya contestado a otro registro (a menudo llamado Usuario).
2. **Habeas.** Si el número sí es el de la ficha y no ha escrito *acepto*, el menú responde el pedido de autorización. Eso deja una salida con canal Meta. En estas fichas esa salida no existe.
3. **El chat no es el número conectado a Cloud API.** Con el menú en Meta, un mensaje al número viejo de Twilio se acepta y no se responde.
4. **Firma.** Si el secreto de la app no coincide con el de Meta, el POST se rechaza antes de guardar. La línea sí está recibiendo a otras personas, así que la firma no está rechazando todo el tráfico.

No es un fallo de entrega tipo `131026`: ese código aparece cuando nosotros escribimos y WhatsApp no entrega. Aquí el hueco es que esas fichas no tienen tráfico de Meta.

---

## 9. Operar sin perderse

- Plan de la organización: Cliente → Plan línea Meta. El grupo puede pisarlo.
- Curso en el carrusel: marcar **En el menú de Formación**.
- Agentes: el conocimiento nuevo entra al prompt cuando alguien lo aprueba en el admin.
- Número interno de prueba: el de siempre en la guía larga (`573026480629`). No usar el de un cliente en sesión real.
- Plantillas: la cuenta en uso es la del 9158 (`531283293408942`). Los cuatro textos ya están aprobados; el carrusel espera `WHATSAPP_APP_ID`.
- Admin sin iconos (se leen palabras como `home` o `unfold_more`): un `setenv` vuelve a desplegar el zip sin la carpeta `staticfiles/` y no corre `collectstatic`. Las fuentes de Unfold responden 404 y el CSS que Cloudflare tenía en caché sigue viéndose a medias. El gancho `.platform/confighooks/predeploy/02_collectstatic.sh` regenera los estáticos en ese caso. Hasta que ese gancho esté en un deploy, no conviene otro `setenv`.

---

## 10. Lecturas

| Documento | Para qué |
|-----------|----------|
| `docs/GUIA_PLATAFORMA_EKI.md` | Mapa largo (contenido, drip, aula, campañas). La sección 26 quedó alineada a octubre; el resto de julio sigue como historia. |
| `docs/AUDITORIA_ARQUITECTURA_EKI.md` | Cómo está armado el código y qué deuda queda. |
| `docs/NAT_GUIA_COMPLETA.md` | Bot comercial de una organización. |
| `docs/EKI_UNFOLD_ADMIN.md` | Consola del equipo. |
| `docs/EKI_STUDIO.md` | Vitrina y checkout. |
| `docs/EKI_APRENDE_REFERENCES.md` | Aula. |
