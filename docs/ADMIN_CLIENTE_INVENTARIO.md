# Inventario del admin de Cliente (antes del rediseño)

Fecha: 2026-10-10. Fuente: `core/admin/clientes.py`, `portal/forms.py` (`ClientePortalAdminForm`), `core/models.py` (`Cliente`) y plantilla `templates/admin/core/cliente/change_form.html`.

Esto es un mapa de lo que existe. No cambia datos ni comportamiento. El rediseño de interfaz espera OK.

Unfold instalado y leído: **django-unfold 0.102.0** en `Python314\Lib\site-packages\unfold` (`django_unfold-0.102.0.dist-info`).

## Cómo está armada la ficha hoy

`ClienteAdmin` usa Unfold (`core/admin/_common.py` sustituye `admin.ModelAdmin`). La plantilla es `admin/core/cliente/change_form.html`, que extiende `admin/eki_collapsible_change_form.html`.

Hay **dos niveles** de pestañas, no uno:

1. Barra principal de Unfold (`tab=True` en los inlines): General, y una pestaña por inline.
2. Dentro de General, fieldsets con `classes: ['tab']`. El primero, **Datos y logo**, no lleva esa clase: queda siempre visible encima de las pestañas de fieldset.

El formulario real es `ClientePortalAdminForm`. Guarda `portal_productos` como texto separado por comas a partir de las casillas `portal_modulos`. Logo y fondo se suben a S3 en `sync_media_fields` después de guardar.

## Desplegable «Ir a sección»

Está en `templates/admin/eki_collapsible_change_form.html` (bloque `form_top`): un `<select id="eki-form-section-select">` con una sola opción fija, «— Elija una sección —».

`static/admin/js/eki_admin_ui.js` (`initSectionNav`) solo rellena ese select si existe `#jazzy-collapsible` y lee los títulos `.card-title`. Eso es el acordeón de Jazzmin. El change form de Unfold no tiene ese nodo, así que **el desplegable se ve y queda vacío**. No navega a ninguna sección.

Los títulos que el JS habría listado con Jazzmin son los de los fieldsets y, si el acordeón los pintaba como cards, los de los inlines:

| Título que existía como sección |
|---|
| Datos y logo |
| Portal y acceso |
| Aula Aprende |
| WhatsApp y legal |
| Certificados y drip |
| Ventanas por fechas |
| Nat e IA |
| Usuarios del portal |
| FAQ organización (PQRS — no curso) |
| Ritmo drip por curso |
| Calendario de módulos |
| Catálogo de productos (Nat) |

En Unfold esas secciones ya están en las dos barras de pestañas de arriba. El desplegable no añade nada.

## Campos del modelo `Cliente`

«Editable hoy» = sale en el formulario de cambio. `ClientePortalAdminForm.Meta.exclude` saca cuatro campos del form. `fecha_registro` no está en ningún fieldset.

| Campo | Tipo | Dónde está hoy | Pestaña nueva | Notas |
|---|---|---|---|---|
| `nombre` | CharField | Datos y logo | 1. Datos | |
| `nit` | CharField | Datos y logo | 1. Datos | Etiqueta NIT/RUT |
| `contacto_principal` | CharField | Datos y logo | 1. Datos | |
| `email` | EmailField | Datos y logo | 1. Datos | |
| `telefono` | CharField | Datos y logo | 1. Datos | |
| `activo` | Boolean | Datos y logo | 1. Datos | Ayuda actual: si está inactivo, sus estudiantes no reciben mensajes |
| `notas_internas` | TextField | Datos y logo | 1. Datos | |
| `es_demo` | — | No existe | 1. Datos | Campo nuevo. Ver migraciones. No se marca nadie hasta confirmación |
| `fecha_registro` | DateTime auto_now_add | No está en el formulario | 1. Datos, solo lectura | No es editable. Lista de excluidos del test de cobertura |
| `logo_url` | URLField | Datos y logo | 2. Marca | El form lo etiqueta «O pegar URL del logo» |
| `portal_subtitulo` | CharField | Portal y acceso | 2. Marca | |
| `wallpaper_aula_url` | URLField | Aula Aprende | 2. Marca | El form lo etiqueta «O pegar URL pública» |
| `fecha_inicio_suscripcion` | Date, null | Portal y acceso | 3. Suscripción y plan | |
| `fecha_fin_suscripcion` | Date, null | Portal y acceso | 3. Suscripción y plan | `suscripcion_activa`: activo y (sin fecha fin, o hoy ≤ fin) |
| `cupos_portal` | PositiveInteger, default 5 | Portal y acceso | 3. Suscripción y plan | El resumen usado/total/restante sigue en el bloque de accesos (pestaña 6) |
| `plan_linea_meta` | CharField choices, blank | Datos y logo | 3. Suscripción y plan | Valores guardados: `curso_asesor`, `dos_cursos`, `asesor_60`, o vacío. Ver aviso de copy más abajo |
| `tipo_proyecto` | choices cursos/gei/nat | Portal y acceso | 4. Productos y canales | Si `portal_productos` va vacío, el portal usa solo este tipo |
| `portal_productos` | CharField | No es widget. Lo escriben las casillas `portal_modulos` | 4. Productos y canales | Formato guardado: `cursos,gei,nat,empleabilidad` sin espacios, o `''`. No se migra |
| `numero_whatsapp_nat` | CharField | Nat e IA | 4. Productos y canales | Validación de formato y aviso de duplicado: solo UI. La regla de negocio del webhook no cambia |
| `numero_whatsapp_autorizado` | CharField | WhatsApp y legal | 4. Productos y canales | |
| `whatsapp_numero` | CharField unique null | Portal y acceso | 4. Productos y canales | Distinto de Nat y del número Meta |
| `twilio_account_sid` | CharField null | WhatsApp y legal | 4. Productos y canales | Secreto. Misma pestaña, bloque aparte |
| `twilio_auth_token` | CharField null | WhatsApp y legal | 4. Productos y canales | Secreto |
| `twilio_whatsapp_from` | CharField null | WhatsApp y legal | 4. Productos y canales | |
| `enlace_habeas_data` | URLField | WhatsApp y legal | 4. Productos y canales | |
| `content_sid_habeas_data_twilio` | CharField | WhatsApp y legal | 4. Productos y canales | |
| `enlace_grupo_whatsapp` | URLField | WhatsApp y legal | 4. Productos y canales | |
| `gei_factores_json` | JSONField | **No está en ningún fieldset** | 4. Productos y canales | Hoy el admin no lo muestra. Se añade aquí para no perderlo. Avisado |
| `modo_gamificacion` | CharField choices | Certificados y drip | 5. Enseñanza | El form lo pinta como radio, no como select |
| `usar_gamificacion` | Boolean | Certificados y drip, solo lectura | 5. Enseñanza | Excluido del form. `Cliente.save` lo sincroniza desde `modo_gamificacion`. No se edita |
| `drip_modulos_solo_estudiantes_listados` | Boolean | Certificados y drip | 5. Enseñanza | |
| `peso_gamificacion_reto` | Decimal | **Excluido del form** | 5. Enseñanza, solo lectura | Hoy no se edita. No lo vuelvo input: un POST podría pisar el peso. Avisado |
| `peso_gamificacion_abierta` | Decimal | **Excluido del form** | 5. Enseñanza, solo lectura | Igual que el peso de reto |
| `enviar_certificados_email` | Boolean | Certificados y drip | 5. Enseñanza | |
| `exigir_nota_minima_certificado` | Boolean | Certificados y drip | 5. Enseñanza | |
| `nota_minima_certificado` | Decimal | Certificados y drip | 5. Enseñanza | |
| `modo_avance_modulo` | choices texto/boton/ambos | WhatsApp y legal | 5. Enseñanza | |
| `content_sid_boton_listo` | CharField | WhatsApp y legal | 5. Enseñanza | |
| `habilitar_pregunta_abierta_final` | Boolean | Ventanas por fechas | 5. Enseñanza | |
| `fecha_inicio_pregunta_abierta_final` | Date null | Ventanas por fechas | 5. Enseñanza | |
| `fecha_fin_pregunta_abierta_final` | Date null | Ventanas por fechas | 5. Enseñanza | |
| `habilitar_gamificacion_proximidad` | Boolean | Ventanas por fechas | 5. Enseñanza | |
| `fecha_inicio_gamificacion_proximidad` | Date null | Ventanas por fechas | 5. Enseñanza | |
| `fecha_fin_gamificacion_proximidad` | Date null | Ventanas por fechas | 5. Enseñanza | |
| `empleabilidad_exploracion_activa` | Boolean | Nat e IA | 8. Catálogo Nat | No hay pestaña «Nat / IA». Caen aquí, en un bloque separado del catálogo |
| `empleabilidad_radio_metros` | PositiveInteger | Nat e IA | 8. Catálogo Nat | |
| `empleabilidad_cooldown_horas` | PositiveInteger | Nat e IA | 8. Catálogo Nat | |
| `empleabilidad_max_misiones_dia` | PositiveInteger | Nat e IA | 8. Catálogo Nat | |
| `empleabilidad_puntos_validacion` | PositiveInteger | Nat e IA | 8. Catálogo Nat | |
| `nombre_agente_tutor` | CharField | Nat e IA | 8. Catálogo Nat | |
| `nombre_agente_asistente` | CharField | Nat e IA | 8. Catálogo Nat | |
| `perfil_facilitador` | choices claudia/tecnicoagro | Nat e IA | 8. Catálogo Nat | |
| `nombre_bot` | CharField | Nat e IA | 8. Catálogo Nat | |
| `system_prompt_extra` | TextField | Nat e IA | 8. Catálogo Nat | |
| `desactivar_llm_comercial` | Boolean | Nat e IA | 8. Catálogo Nat | |

### Campos que no son columnas (formulario)

| Control | Dónde está hoy | Pestaña nueva | Qué escribe |
|---|---|---|---|
| `portal_modulos` | Portal y acceso. Casillas: Cursos eki, Inventario GEI, Agente Nat, Empleabilidad territorial | 4. Productos y canales | `portal_productos` unido por comas, en el orden de las casillas marcadas. Vacío si no hay ninguna |
| `logo_archivo` | Datos y logo | 2. Marca | Un solo control: archivo, o URL, o quitar. Sigue llamando a `guardar_logo_organizacion` |
| `quitar_logo` | Datos y logo | 2. Marca | Vacía `logo_url` |
| `wallpaper_archivo` | Aula Aprende | 2. Marca | `guardar_wallpaper_aula` |
| `quitar_wallpaper` | Aula Aprende | 2. Marca | Vacía `wallpaper_aula_url` |

`PORTAL_PRODUCTO_CHOICES` en `portal/forms.py` tiene exactamente cuatro claves: `cursos`, `gei`, `nat`, `empleabilidad`. No hay más en el código del portal (`MODULOS_VALIDOS` es el mismo conjunto).

### Bloques de solo lectura (no son columnas)

| Método | Dónde está hoy | Pestaña nueva | Qué hace |
|---|---|---|---|
| `logo_preview` | Datos y logo | 2. Marca | La sustituye el panel «Así se ve» |
| `wallpaper_preview` | Aula Aprende | 2. Marca | Igual |
| `mapa_cobertura_rapido` | Datos y logo. Enlace «Mapa →» a `admin_cobertura_mapa?cliente=` | 9. Cobertura | La vista ya existe (`core/views_cobertura_admin.py`) y trae `por_departamento` |
| `portal_usuarios_acciones` | Portal y acceso | 6. Personas | Cupos usados/total/restantes, crear usuario, ver usuarios, abrir portal. La URL custom no se toca |
| `cobertura_y_drip_acciones` | Certificados y drip | 5. Enseñanza | Enlaces: mapa, acceso módulos, ajustar avance, gamificación manual, certificados presenciales, push, formulario externo |
| `empleabilidad_kpis_resumen` | Nat e IA | 8. Catálogo Nat | Retención, misiones, oportunidades, enlaces a misiones/aliados/portal |

`numero_meta_badge` está definido en `ClienteAdmin` y **no está en `list_display`**. No se muestra. No se borra el método en este rediseño; tampoco entra al listado nuevo.

## Inlines de la ficha

Todos con `tab=True` (barra principal de Unfold).

| Inline | Modelo | Campos en la fila | Dónde está hoy | Pestaña nueva |
|---|---|---|---|---|
| `PortalUsuarioInline` | `portal.PortalUsuario` (`organizacion`) | `user`, `rol`, `debe_cambiar_credenciales`, `password_temporal` (lectura), `portal_user_link` (lectura) | Pestaña de inline | 6. Personas |
| `FaqOrganizacionInline` | `core.FaqOrganizacion` | `pregunta`, `respuesta`, `palabras_clave`, `orden`, `activo` | Pestaña de inline | 7. Atención PQRS |
| `ConfiguracionDripClienteInline` | `core.ConfiguracionDripCliente` | `curso`, `dias_espera_entre_modulos`, `activo` | Pestaña de inline | 5. Enseñanza |
| `HabilitacionModuloDripClienteInline` | `core.HabilitacionModuloDripCliente` | `curso`, `modulo`, `habilitado_desde`, `activo` | Pestaña de inline | 5. Enseñanza. Si la tabla crece, enlace con conteo al mismo inline paginado (`per_page`), no se quita |
| `ProductoCatalogoInline` | `core.ProductoCatalogo` | `nombre`, `sku`, `categoria`, `cultivos_objetivo`, `precio_cop`, `unidad`, `url_producto`, `activo`. `show_change_link` | Pestaña de inline | 8. Catálogo Nat, paginado |

Roles de `PortalUsuario.rol`: `admin`, `profesor`, `viewer`, `eki_ops`. Esos cuatro niveles se quedan.

`HabilitacionModuloEstudianteInline` está en `clientes.py` pero **no es inline de Cliente**. Lo usa `EstudianteAdmin`. El modelo apunta a `estudiante`, no a `cliente`. No se mueve a esta ficha.

### Campos de `ProductoCatalogo` que el inline no muestra

Siguen en `ProductoCatalogoAdmin` (ficha propia, enlace «cambiar»): `imagen`, `descripcion`, `problema_que_resuelve`, `ingrediente_activo`, `dosis`, `fecha_actualizacion`. El inline no los absorbe: hoy ya se editan en esa ficha y el enlace se conserva.

### `ProductoComercial`

Existe (`core.ProductoComercial`, admin propio con importación de precios). **No es inline de Cliente.** Propuesta: inline paginado en la pestaña 8, con los campos del admin de precios, sin tocar la importación Excel (sigue en su changelist). Avisado: es superficie nueva sobre un modelo que ya se editaba en otra pantalla.

## Relaciones que no son inline

No se convierten en tablas editables. Entran como enlace con conteo, para no cambiar cómo se crean.

| Relación | Modelo | Dónde está hoy en la ficha | Pestaña nueva |
|---|---|---|---|
| Estudiantes | `Estudiante.cliente` | Cifra en el encabezado (`activo=True`) | Encabezado + 6. Personas (enlace al listado `?cliente=`) |
| Cursos | `Curso.cliente` | Cifra en el encabezado (`activo=True`) | Encabezado + columna del listado |
| Campañas | `Campana.cliente` | Cifra y última campaña en el encabezado | Encabezado + 10. Actividad (enlace filtrado) |
| Grupos | `GrupoEstudiantes.cliente` | No está en la ficha | 6. Personas, enlace con conteo |
| Campañas Meta | `CampanaMeta.cliente` | No está | 10. Actividad, enlace con conteo. Avisado |
| Campañas únicas | `CampanaUnica.cliente` | No está | 10. Actividad, enlace con conteo. Avisado |
| Push | `MensajePush.cliente` | Enlace dentro de `cobertura_y_drip_acciones` | 5. Enseñanza (el mismo enlace) |
| Formulario externo | `EnlaceFormularioExterno.cliente` | Enlace en el mismo bloque | 5. Enseñanza |
| FAQ PQRS | `FaqOrganizacion` | Inline | 7 |
| Métricas empresa / Nat | `MetaMetricaEmpresa`, `MetaMetricaNati` | No están en la ficha | No se editan aquí. Quedan en sus admins |
| RAG comercial | `DocumentoRAGComercial` | No está. La acción masiva copia conocimiento | 10. Actividad, solo el enlace si hace falta. La acción masiva se conserva en el listado |
| Biblioteca Nat | `BibliotecaConocimiento` | No está | Igual: no se incrusta |
| Certificados (plantilla) | `PlantillaCertificado.cliente` | Enlace «Certificados presenciales» | 5. Enseñanza |
| Aliados y misiones | `AliadoEmpleabilidad`, `MisionEmpleabilidad` | Enlaces del bloque de KPIs | 8. Catálogo Nat |
| Eventos | `EstudianteEventoAprendizaje`, `EventoIA` | No están | 10. Actividad no los lista todos. «Sin dato» si no hay un listado ya filtrable |
| Sesión comercial | `SesionComercial` | No está | 10. Actividad, no se incrusta |
| Candidatas RAG | `ConversacionRAGCandidata` | No está | Fuera de la ficha |
| Uso LLM | `UsoLLM` | No está | Fuera de la ficha |
| Tipo de formulario / ficha GEI | `formulario.TipoFormulario`, `FichaGEI` | No está | Fuera de la ficha |
| Portal | `PortalUsuario`, `PortalFeedback`, `PortalSugerenciaIA` | Solo el inline de usuarios y los botones de acceso | 6. Personas. Feedback y sugerencias no se incrustan |
| Margen y mercado | `CalculoMargen`, `MargenUsoEvento`, `MargenEnlaceCliente`, `EscenarioMercado` | No están | Fuera de la ficha |
| WhatsApp | `WhatsappLog` no tiene FK a Cliente. Se busca por teléfono de los estudiantes (hoy, como máximo 500 teléfonos) | Encabezado: último mensaje | Encabezado + columna del listado + 10. Actividad |

`simple_history` no está instalado ni hay `HistoricalCliente`. El historial de la pestaña 10 es el de Django admin (`LogEntry`, `SHOW_HISTORY = True` en `UNFOLD`).

`PQRS` cuelga del estudiante, no del cliente. La pestaña 7 es solo el inline de FAQ de organización.

## Listado hoy

| Pieza | Valor hoy | Qué pasa en el rediseño |
|---|---|---|
| `list_display` | `logo_thumb`, `nombre`, `activo`, `plan_linea_meta`, `estudiantes_activos`, `cursos_asignados` | Columnas nuevas del encargo. Logo o inicial se conserva |
| `list_filter` | `activo`, `plan_linea_meta` | Se suman producto, suscripción (vigente / por vencer / vencida) y demo |
| `search_fields` | `nombre`, `nit`, `contacto_principal`, `email` | Igual |
| `ordering` | `nombre` | Igual |
| `list_per_page` | 50 | Igual |
| `compressed_fields` | True | Igual |
| Conteos | `total_estudiantes()` y `total_cursos()` por fila (una consulta por celda) | Un `annotate` en `get_queryset`. El número de consultas no crece con las filas |
| Último WhatsApp | No está en el listado. En la ficha recorre teléfonos | Subquery por cliente, no un query por fila |
| Barra de avance | No existe. `ProgresoEstudiante.porcentaje_avance()` hace consultas por curso | Una expresión agregada en el mismo queryset. Si no se puede igualar al método sin consultas por fila, la celda dice «Sin dato» |

## Acciones, URLs y permisos

| Acción | Dónde | Se conserva |
|---|---|---|
| Añadir (botón Unfold del listado) | Changelist, `show_add_link` | Sí. Además `actions_list` «Nuevo cliente» apunta a la misma URL de alta |
| `copiar_todos_cursos_a_analytics_pruebas` | Acción masiva. Exige un solo cliente y que sea el origen Analytics | Sí, al final del menú |
| `copiar_conocimiento_nati_desde_agronexo` | Acción masiva sobre destinos | Sí |
| `delete_selected` | Acción masiva por defecto de Django | Sí en el listado. El botón Eliminar de la barra de la ficha sale de ahí y pasa a la zona de peligro |
| Guardar / Guardar y continuar / Guardar y añadir otro | Barra fija de Unfold (`submit_line.html`, ya es `lg:sticky`) | Mismos `name`: `_save`, `_continue`, `_addanother` |
| Eliminar en la ficha | Enlace al delete de Django si `has_delete_permission` | Deja la barra. Zona de peligro: bloqueado si hay estudiantes, cursos o campañas; si está vacío, hay que escribir el nombre |
| `crear_usuario_portal_view` | `admin:core_cliente_crear_usuario_portal`. Exige `has_change_permission` sobre ese cliente | Igual |
| Exportar | **No existe** | `actions_list` nuevo. Solo lectura |
| Asignar plan de línea Meta | **No existe** | Acción masiva nueva. Escribe `plan_linea_meta` con el mismo choice de hoy. El diálogo de Unfold `@action(dialog=)` no recibe queryset: la confirmación (organizaciones y estudiantes afectados) es una vista intermedia, al estilo de `delete_selected` |
| Abrir / Ver estudiantes / Ver campañas | La fila ya abre la ficha. No hay acciones de fila | `actions_row` de Unfold. Ver estudiantes y ver campañas son enlaces filtrados, no pantallas nuevas |

Permisos: `ClienteAdmin` no redefine `has_add/change/delete/view_permission`. Siguen `core.add_cliente`, `core.change_cliente`, `core.delete_cliente`, `core.view_cliente`.

Cada inline usa los permisos de su modelo (`portal.*_portalusuario`, `core.*_faqorganizacion`, `core.*_configuraciondripcliente`, `core.*_habilitacionmodulodripcliente`, `core.*_productocatalogo`). Quien no puede ver el modelo no recibe el inline (`get_inline_instances`). En la ficha nueva, esa pestaña no se renderiza.

No hay `save_as`, `list_editable`, `date_hierarchy` ni `autocomplete` en el modelo Cliente. Los autocomplete están en los inlines (`curso`, `modulo`, `user`).

## Encabezado de la ficha (ya existe, se mueve)

`change_view` ya calcula estudiantes activos, cursos activos, campañas, última campaña y último `WhatsappLog` de hasta 500 teléfonos. La plantilla pinta logo o inicial, nombre, badge activo/inactivo, tipo de proyecto, contacto, correo, NIT y esas cifras.

Pasa a `change_form_before_template`. Se añaden chips de productos y de plan. Se quita el desplegable. La barra de guardado sigue siendo la de Unfold.

## Copy del plan vacío (no es un cambio de lógica)

El encargo pide el tooltip «usa OP1 por defecto». El código no hace eso siempre:

- `Cliente.plan_linea_meta` vacío y `LINEA_META_PLAN_DEFAULT` vacío (el default de `settings.py`) → `resolver_plan` devuelve sin plan: no abre cursos nuevos ni el asesor. Los cursos ya empezados siguen.
- Si el entorno tiene `LINEA_META_PLAN_DEFAULT=curso_asesor`, entonces sí cae en OP1.
- Un grupo con `GrupoEstudiantes.plan_linea_meta` gana sobre la organización. La suscripción vencida (`fecha_fin_suscripcion` &lt; hoy) apaga el plan del grupo y el de la organización (`suscripcion_vencida`).
- Cliente inactivo: la ayuda del campo dice que sus estudiantes dejan de recibir mensajes. El plan, además, no se resuelve si `cliente.activo` es falso.

Propuesta de texto, a confirmar: el chip «Sin plan» y el tooltip leen el setting. Si el default está vacío, el tooltip dice que no hay plan (no abre cursos nuevos ni el asesor). Si el default es OP1, dice que usa OP1. No se cambia `resolver_plan`.

Al vencer la suscripción, la ficha muestra el chip rojo y el texto de `_causa_sin_plan`: suscripción vencida. No se inventa otro efecto.

## Qué pide el listado y de dónde sale

| Pedido | Fuente | Si no se puede |
|---|---|---|
| Pestañas Todos / Reales / Demo / Sin plan Meta / Inactivos, con conteo | Filtros sobre `activo`, `es_demo`, `plan_linea_meta` | Conteos en el título. Ver límite de Unfold abajo |
| Organización: logo o iniciales, nombre, «Activo · hace N días» | `logo_url` o `logo_estatico_para_nombre`; último `WhatsappLog.fecha` de los teléfonos de sus estudiantes | Sin mensajes: «Sin dato» |
| Etiqueta Demo | `es_demo` | Nadie queda marcado hasta el OK de la lista |
| Plan: chip OP1/OP2/OP3 o ámbar «Sin plan» | `plan_linea_meta` | Tooltip según el setting, no un OP1 fijo |
| Productos: chips | `portal_productos` partido por coma. Si vacío, el chip es el `tipo_proyecto` (así se comporta el portal) | |
| Estudiantes y barra | `Count` de estudiantes activos y promedio de avance en una sola query | Barra «Sin dato» si el promedio no cabe en el annotate |
| Cursos | `Count` de cursos | |
| Suscripción | Días hasta `fecha_fin_suscripcion`. Ámbar &lt; 30, rojo si ya pasó. Sin fecha: «Sin dato» | No se trata «sin fecha» como vencida: `suscripcion_activa` en ese caso mira solo `activo` |

## APIs reales de Unfold 0.102.0

Confirmadas en el paquete instalado, no en la documentación web.

| Pedido | Nombre real | Dónde |
|---|---|---|
| Pestañas del listado | `UNFOLD["TABS"]` | `unfold/settings.py` default `[]`. `UnfoldAdminSite.get_tabs_list`. Cada bloque tiene `models` e `items` (`title`, `link`, `active` opcional, `permission` opcional). Para el changelist, `models` es el string `"core.cliente"`. Para la ficha, `models` es `{"name": "core.cliente", "detail": True}` |
| Conteo en esas pestañas | No hay `badge` en `tab_items.html` | El badge de Unfold existe en el sidebar (`app_list_badge.html`), no en las pestañas del changelist. El conteo va dentro de `title` |
| Fieldsets con pestañas | `classes: ['tab']` en el fieldset | Filtro de plantilla `tabs`. Se ven solo con `activeTab == 'general'` (`fieldsets_tabs.html`). El punto rojo de error es `tabs_errors_count` |
| Inlines con pestañas | `tab = True` en el inline | `unfold/admin.py` `BaseInlineMixin.tab`. Si no hay `TABS` de ficha, la barra principal es «General» más cada inline |
| Paginación de inline | `per_page = N` | `PaginationInlineFormSet`, querystring `{prefix}-page` |
| Conteo en la pestaña del inline | `show_count = True` y opcional `get_count` | `get_formset_kwargs` |
| `actions_list` | Atributo del ModelAdmin | Mixin `ActionModelAdminMixin`. Decorador `unfold.decorators.action` |
| `actions_row` | Igual, una por fila | URL `<object_id>/{path}/` |
| Acciones masivas | `actions = [...]` de Django | Siguen siendo acciones de queryset. El diálogo `dialog=` del decorador Unfold **no** recibe el queryset |
| `conditional_fields` | No está declarado en la clase | La plantilla `admin/change_form.html` lo consulta. Si el ModelAdmin define un dict `{nombre_campo: expresion_alpine}`, `fieldset_row.html` pone `x-show`. Filtro `changeform_data` |
| `change_form_before_template` | Atributo, default `None` | Se incluye dentro del `<form>` en `admin/change_form.html` |
| `list_before_template` | Atributo, default `None` | Se incluye en `admin/change_list.html` si no es popup |
| Barra de guardado | `templates/admin/submit_line.html` | Ya es sticky en `lg`. También existen `actions_submit_line` y `change_form_outer_before_template` |

Límite para las diez pestañas de la ficha: Unfold no mezcla fieldsets e inlines en la misma barra. Los fieldsets con `tab` viven dentro de General; los inlines con `tab=True` son otra barra y, al activarlos, ocultan General. La ficha de Cliente va a usar una plantilla propia que pone **una** barra y asigna `activeTab` / `activeFieldsetTab`, que son las variables que Unfold ya usa para mostrar y ocultar. No se inventa otro mecanismo.

Al guardar con error, Unfold ya marca el conteo en la pestaña de fieldset y en la del inline. La plantilla de Cliente, además, activa la primera pestaña con error.

## Textos que siguen en inglés en 0.102.0

El paquete no trae `locale/es`. Con `LANGUAGE_CODE = es-co`, las cadenas propias de Unfold no se traducen solas. Hay que cubrir al menos:

- `Select value` (`unfold/mixins/formfield_model_admin.py`)
- `Type to search` (buscador y paleta de comandos)
- `Filters`, `Apply Filters`, `Clear all filters`
- `Select action` (`unfold/admin.py`, `get_action_choices`)
- `General` (pestaña automática de inlines)
- `Save`, `Save and continue editing`, `Save and add another`, `Delete`, `Close`, `Add another` (si el catálogo de Django en español no las cubre en este admin)

Estilo: variables de Unfold y tonos Cielo / Marca / Oscuro que ya carga el admin. Sin degradados ni sombras decorativas.

## Interruptor

`ADMIN_CLIENTES_V2`, variable de entorno, default falso. Con falso queda registrado el `ClienteAdmin` actual, sin cambios de comportamiento. El modelo nuevo no reemplaza al viejo hasta que se apruebe borrar el viejo.

El campo `es_demo` sí lo lee el ORM en cuanto está en el modelo, aunque el interruptor esté apagado. La migración tiene que estar aplicada en ese entorno antes de correr el código nuevo. El interruptor solo elige la interfaz.

## Migración propuesta (no aplicada)

| Campo | Definición | Migración |
|---|---|---|
| `es_demo` | `BooleanField(default=False)` | `AddField` con default. Compatible hacia atrás: el rollback de código deja la columna. Nadie queda en demo hasta un UPDATE confirmado |

No hay otra columna. Suscripción, productos, plan y último mensaje se calculan. `portal_productos` no se migra.

No se aplica en ninguna base hasta el OK. En local tampoco, hasta ese OK.

## Lista explícita para el test de cobertura

El test recorre campos editables del modelo y de los inlines. Falla si falta alguno en el formulario nuevo, salvo:

| Excluido | Motivo |
|---|---|
| `id` | Clave primaria. No es un campo del formulario |
| `fecha_registro` | `auto_now_add`. Solo lectura en Datos, no es input |
| `usar_gamificacion` | Lo escribe `Cliente.save` desde `modo_gamificacion`. Sigue visible en solo lectura |
| `peso_gamificacion_reto` | El form actual lo excluye. Solo lectura en Enseñanza para no abrir un campo que hoy un guardado no toca |
| `peso_gamificacion_abierta` | Igual |
| `portal_productos` | No es input. Lo cubre el test de casillas (`portal_modulos` → el mismo texto) |

`gei_factores_json` **no** está en esta lista: hoy no se muestra y el rediseño lo enseña en Productos y canales.

## Volcado local (no está en git)

SQLite local (`db.sqlite3`). No es RDS. `backups/` está en `.gitignore` (regla `backups/`).

Carpeta: `backups/admin_cliente_20261010/`.

| Archivo | Resultado |
|---|---|
| `core_Cliente.json` | dumpdata, 33 filas |
| `core_FaqOrganizacion.json` | dumpdata |
| `core_Curso.json` | dumpdata (hizo falta UTF-8 por un emoji) |
| `core_Campana.json` | dumpdata, vacío de filas con datos útiles (0 campañas con cliente en el conteo ORM; el archivo existe) |
| `core_ProductoCatalogo.json` | dumpdata, 4 productos |
| `core_ProductoComercial.json` | dumpdata, 0 filas |
| `core_SesionComercial.json` | dumpdata |
| `core_EventoIA.json` | dumpdata |
| `core_ConfiguracionDripCliente.json` | dumpdata, 0 filas |
| `core_HabilitacionModuloDripCliente.json` | dumpdata, 0 filas |
| `formulario_FichaGEI.json` | dumpdata |
| `portal_PortalUsuario.json` | dumpdata |
| `core_estudiante_sqlite.json` | SQL directo. dumpdata falló: a la tabla local le falta `rural_disperso` |
| `core_whatsapplog_sqlite.json` | SQL directo. Falta la columna `canal` respecto al modelo |
| `core_grupoestudiantes_sqlite.json` | SQL directo, 2 filas. Falta `plan_linea_meta` |
| `formulario_tipoformulario_sqlite.json` | SQL directo. Falta `meta_flow_id` |

Esa SQLite está detrás del modelo en esas cuatro tablas. No corrí migraciones.

Mojibake: 0 coincidencias en las columnas de texto de `core_cliente`, `core_curso`, `core_estudiante` y `core_grupoestudiantes` en esta copia. El comando `--dry-run` igual tiene que mirar producción o una copia fiel; aquí no hay «Usaquén» roto que corregir.

Staging y producción no se volcaron.
