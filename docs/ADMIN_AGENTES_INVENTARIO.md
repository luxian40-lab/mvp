# Inventario del admin de agentes

Fecha: 12 de octubre de 2026. Unfold `django-unfold==0.91.0` (requirements). Nada de esto cambia el prompt, el RAG ni Nat. El interruptor `ADMIN_AGENTES_V2` nace apagado. Un superusuario lo ve con `?ui=v2`.

## Los agentes no son un modelo

Viven en código, en `FILAS_AGENTES` de `core/sandbox_menu.py`.

| Clave en el menú | Nombre | Dónde aprende hoy |
|---|---|---|
| `nat` | Agrónomo eki | Nat / bot comercial. Knowledge Studio y RAG comercial. No es una fila de `ConocimientoAgente`. |
| `coach` | Coach eki | `ConocimientoAgente` (`coach`) |
| `profe` | Profesor IA | En el menú es `profe`. En el conocimiento el código es `ia_campo` (Profe IA). |
| `ventas` | Ventas eki | `ConocimientoAgente` (`ventas`) |
| `finanzas` | Experto en finanzas | `ConocimientoAgente` (`finanzas`) |
| `cafe` | Experto en café | `ConocimientoAgente` (`cafe`). No estaba en la lista original de cinco; sí está en el menú y en el conocimiento. |

No hay ficha ni panel nativos de Unfold mientras no exista un modelo. No propongo un modelo proxy ni una migración hasta que usted lo autorice. El Panel y el Laboratorio, si siguen sin modelo, necesitan una página que extienda el layout de Unfold. Eso se pide aparte.

## Qué guarda cada pieza y a qué pantalla iría

| Qué | Dónde está | Qué guarda | Cómo entra al agente | Pantalla nueva |
|---|---|---|---|---|
| Conocimiento de agentes | `core/models_agentes.py`, admin `core/admin/agentes.py` | Un agente (o Todos), tipo dato/regla, título, contenido, estado sugerido/aprobado/descartado, origen, pregunta y respuesta de origen, `revisado_por`, alcance Todos o Un cliente. No hay vigencia, ni usos, ni utilidad. | `bloque_conocimiento` arma el texto de los aprobados y lo cachea 5 minutos. Lo de un cliente solo entra para esa organización. Entra al prompt al aprobar. No hay paso «Publicar cambios». | Ficha, pestaña Conocimiento. Los sugeridos también salen en la Bandeja. |
| Captura desde conversación | `capturar_sugerencia` | Muestra al azar (`AGENTES_CAPTURA_PORCENTAJE`, 15). Enmascara correo y números largos. No enmascara nombres ni cédulas si no vienen como número. | No entra al prompt hasta que el estado sea aprobado. | Bandeja, pestaña Sugeridos. |
| Knowledge Studio | `core/views_knowledge_studio.py`, `/admin/knowledge-studio/` | Página propia. Lista candidatas HITL y documentos comerciales. | No es el prompt. Publicar indexa RAG comercial. | La Bandeja reemplaza la cola, no borra esta página. |
| Candidata RAG | `ConversacionRAGCandidata` en `core/models.py`. Admin proxy `agents_commercial`. | Pregunta, respuesta de Nat, respuesta revisada, cliente, sesión, **teléfono**, trace, contexto, chunks, estado pendiente/aprobada/rechazada/publicada, `revisado_por`, `fecha_revision`, documento publicado. | `revisar_candidata` y `publicar_candidata_en_rag` en `core/knowledge_studio.py`. Aprobar no publica. Publicar crea el documento RAG comercial. | Bandeja (pantalla 3), ya cableada detrás del interruptor. |
| Documento RAG de curso | `DocumentoRAG` | Archivo, curso, tipo, uso (todos/compañero/claudia), estado pendiente/indexado/error, chunks, quién subió. Sin vigencia. | Cola `rag_index`, tarea `indexar_documento_rag_por_id`. | Biblioteca. |
| Documento RAG comercial | `DocumentoRAGComercial` | Archivo o texto, cliente (vacío = general), canal, tipo, estado pendiente/indexado/error. Legado de Nat. | `rag_comercial_manager` y cola `rag_index`. | Biblioteca. |
| Biblioteca del portal | Portal Nat, documentos del cliente | Los sube la organización en el portal, no esta bandeja. | Indexación Nat. | Biblioteca, solo lectura del lado admin, con el permiso de staff. |
| Catálogo | `ProductoCatalogo` y `ProductoComercial` | Ficha (nombre, SKU, ingrediente, cultivos, problemas) y precio/SKU. Instrucciones extra de Nat viven en el cliente, no en el producto. | El bot comercial los lee. No se reemplazan. | Catálogo. |
| Evento IA | `EventoIA` | Trace, tipo, agente, canal, modelo, latencia, tokens, previews. Admin de solo lectura. | No alimenta el prompt. Sirve para el replay de AI Ops. | Laboratorio, si se registra origen «laboratorio». Hoy no existe ese origen. |
| Impacto | `portal/impacto.py` | Tuplas de indicadores, no modelos `IndicadorImpacto` / `PreguntaImpacto` / `RespuestaImpacto`. | No hay preguntas de impacto por agente. | No se construye hasta que usted lo pida. |
| Versiones | — | No hay `simple_history` en el conocimiento. | — | No hay reversión. Hace falta su autorización. |

## Estados que pidió y lo que hay

| Pedido | Hoy |
|---|---|
| Borrador, Pendiente, Aprobado, Archivado | Conocimiento: sugerido, aprobado, descartado. No hay borrador ni archivado. Candidata: pendiente, aprobada, rechazada, publicada. |
| Alcance Todos o Un cliente | Sí, en la candidata y en el conocimiento (`0181`). El campo agente «Todos» sigue siendo otro asunto: un texto para varios agentes. |
| Vigencia | No existe en conocimiento ni en documentos. |
| Quién aprobó y cuándo | Sí: `revisado_por` y `fecha_revision` (candidata) o `actualizado_en` (conocimiento). |
| Usos y utilidad | No se registran. En la ficha habría que mostrar «Sin dato». |

Migración `0181`: la candidata guarda «Aplica a» y el alcance; el conocimiento guarda alcance y cliente. Lo de alcance Todos sigue entrando al prompt como antes. Lo de Un cliente solo entra si la persona es de esa organización. Vigencia, Borrador y Archivado siguen sin hacerse.

## Privacidad

La candidata guarda el teléfono y el texto crudo de la pregunta. La bandeja v2 no muestra el teléfono y pasa la pregunta por el mismo enmascarado de correo y números que ya usa `capturar_sugerencia`. Los nombres y las cédulas escritas en palabras siguen en el texto. Propuesta, sin hacerla todavía: enmascarar al guardar en `crear_candidata_hitl`, no solo al mostrar.

## Unfold 0.91.0 (paquete instalado)

| Pieza | Evidencia |
|---|---|
| Changelist, `list_before_template`, `actions_row`, `actions_detail`, `actions_list`, `actions_submit_line` | `unfold/admin.py`, `unfold/mixins/action_model_admin.py` |
| `UNFOLD["TABS"]` | `mvp_project/unfold_admin.py` apunta a `core.admin.unfold_tabs.tabs_admin` |
| Inline con pestaña y `show_count` | `unfold/templates/unfold/helpers/inline_count.html` y `show_count` en `unfold/admin.py` |
| `change_form_before_template` / `after` | Opciones de ModelAdmin de Unfold (mismo patrón que `list_before_template`) |
| `conditional_fields` | Sí está en las plantillas `change_form.html` y `fieldset_row.html` de este 0.91.0. El pedido decía que no existía. En este paquete sí. |

## Excluidos de las pantallas nuevas

| Pieza | Motivo |
|---|---|
| `SandboxCanalSesion` | Estado del menú de una persona, no conocimiento. |
| `ContextoAgroSession` | Contexto de una sesión Nat, no una ficha de agente. |
| `EventOutbox`, `SenalTerritorial`, `AlertaTerritorial` | Territorio, no la bandeja. |
| Prompts de `core/nati.py`, `core/prompts_tecnicoagro.py`, `core/agentes_ia.py` | Son código. La ficha no los edita hasta que usted lo pida. Tocarlos cambiaría cómo responden. |
