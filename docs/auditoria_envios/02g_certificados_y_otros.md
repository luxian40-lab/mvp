# 02g — Certificados, portal, GEI, seguimiento, menú sandbox y Nat

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `_enviar_whatsapp_con_reintentos` — `core/certificado_service.py:661`

```python
# core/certificado_service.py:661
def _enviar_whatsapp_con_reintentos(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    pausa_inicial: float = 0.0,
) -> dict:
    """Reintenta envío de sesión (p. ej. imagen del diploma tras plantilla HSM)."""
    from .utils import enviar_whatsapp_twilio

    if pausa_inicial > 0:
        time.sleep(pausa_inicial)

    ultimo: dict = {'success': False, 'response': 'sin respuesta'}
    for intento in range(1, MAX_REINTENTOS_ENVIO_DIPLOMA + 1):
        ultimo = enviar_whatsapp_twilio(
            telefono=telefono,
            texto=texto,
            media_url=media_url,
        )
        if ultimo.get('success'):
            return ultimo
        detalle = str(ultimo.get('response', '')).lower()
        reintentar = any(x in detalle for x in ('63016', '63019', 'window', '24 hour', '24-hour', 'rate', 'media'))
        if intento < MAX_REINTENTOS_ENVIO_DIPLOMA and reintentar:
            time.sleep(2.0 * intento)
            continue
        break
    return ultimo


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_intentar_enviar_imagen_diploma` — `core/certificado_service.py:692`

```python
# core/certificado_service.py:692
def _intentar_enviar_imagen_diploma(
    estudiante,
    certificado,
    *,
    caption: str,
    media_url: str,
    pausa_inicial: float,
) -> tuple[dict, str]:
    """Intenta enviar la imagen del diploma por sesión (con reintentos)."""
    resultado = _enviar_whatsapp_con_reintentos(
        estudiante.telefono,
        caption,
        media_url=media_url,
        pausa_inicial=pausa_inicial,
    )
    if resultado.get('success'):
        return resultado, 'imagen'
    logger.warning(
        '⚠️ Imagen diploma falló para %s: %s',
        certificado.codigo_verificacion,
        resultado.get('response'),
    )
    return resultado, 'fallo'


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_variables_plantilla_media_certificado` — `core/certificado_service.py:717`

```python
# core/certificado_service.py:717
def _variables_plantilla_media_certificado(
    certificado,
    media_url: str,
    media_var_index: str = '1',
) -> dict:
    """
    Variables para plantilla de IMAGEN (header media + texto).
    Por defecto: {{1}} = URL imagen (header), {{2}} = nombre, {{3}} = curso, {{4}} = código.
    """
    est = certificado.estudiante
    curso = certificado.curso
    base = {
        media_var_index: media_url,
        '2': est.nombre or 'estudiante',
        '3': curso.nombre if curso else 'curso',
        '4': certificado.codigo_verificacion or '',
    }
    # Si el header usa otro índice, no pisar el {{1}} de texto del autor.
    base.setdefault('1', media_url)
    return base


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_enviar_plantilla_media_twilio` — `core/certificado_service.py:739`

```python
# core/certificado_service.py:739
def _enviar_plantilla_media_twilio(telefono: str, content_sid: str, variables: dict) -> dict:
    """Wrapper testeable para plantilla con imagen (header media)."""
    from .enviar_plantillas import enviar_plantilla_twilio

    return enviar_plantilla_twilio(telefono, content_sid, variables=variables)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_certificado_whatsapp` — `core/certificado_service.py:746`

```python
# core/certificado_service.py:746
def enviar_certificado_whatsapp(
    certificado,
    *,
    twilio_content_sid_media: str | None = None,
    media_var_index: str = '1',
    twilio_content_sid: str | None = None,
    template_variables: dict | None = None,
    tras_plantilla_previo: bool = False,
):
    """
    Envía el certificado por WhatsApp al estudiante.

    Prioridad de modos:
      0. twilio_content_sid_media → plantilla aprobada CON imagen en el header
         (la URL del PNG va como variable). UN solo mensaje business-initiated que
         entrega el diploma SIN que el estudiante responda. ← modo ideal.
      1. twilio_content_sid / tras_plantilla_previo → plantilla de texto + imagen de
         sesión (solo funciona si la ventana de 24 h está abierta).

    Returns:
        bool: True si se envió exitosamente
    """
    if not certificado.emitido or (not certificado.archivo_pdf and not certificado.archivo_imagen):
        logger.error(f"Certificado {certificado.codigo_verificacion} no está generado")
        return False

    try:
        estudiante = certificado.estudiante
        curso = certificado.curso
        media_url = _media_url_certificado(certificado)
        if not media_url:
            logger.error(f"Certificado {certificado.codigo_verificacion} no tiene archivo")
            return False

        verificacion_url = certificado.obtener_url_verificacion()
        mencion = certificado.obtener_mencion()
        calificacion = float(certificado.calificacion_final)
        vars_tpl = template_variables or _variables_plantilla_certificado(certificado)
        sid_media = (twilio_content_sid_media or '').strip()
        sid = (twilio_content_sid or '').strip()
        pausa = PAUSA_TRAS_PLANTILLA_SEG if tras_plantilla_previo else 0.0
        modo_envio = 'imagen'

        caption_corto = (
            f"🎓 *{estudiante.nombre}* — certificado *{curso.nombre}* "
            f"({calificacion}%). Código: `{certificado.codigo_verificacion}`"
        )
        if mencion:
            caption_corto += f"\n🏆 {mencion}"

        if sid_media:
            # MODO IDEAL: plantilla aprobada con imagen del certificado en el header.
            resultado = _enviar_plantilla_media_twilio(
                estudiante.telefono,
                sid_media,
                _variables_plantilla_media_certificado(
                    certificado, media_url, media_var_index,
                ),
            )
            modo_envio = 'plantilla_imagen'
        elif sid:
            from .enviar_plantillas import enviar_plantilla_twilio

            tpl_res = enviar_plantilla_twilio(
                estudiante.telefono,
                sid,
                variables=vars_tpl,
            )
            if not tpl_res.get('success'):
                logger.error(
                    "❌ Plantilla Twilio diploma falló para %s: %s",
                    certificado.codigo_verificacion,
                    tpl_res.get('response'),
                )
                return False
            resultado, modo_envio = _intentar_enviar_imagen_diploma(
                estudiante,
                certificado,
                caption=caption_corto,
                media_url=media_url,
                pausa_inicial=pausa or PAUSA_TRAS_PLANTILLA_SEG,
            )
        elif tras_plantilla_previo:
            resultado, modo_envio = _intentar_enviar_imagen_diploma(
                estudiante,
                certificado,
                caption=caption_corto,
                media_url=media_url,
                pausa_inicial=pausa,
            )
        else:
            mensaje = f"""🎓 *¡FELICITACIONES {estudiante.nombre.upper()}!* 🎉

Has completado exitosamente el curso:
📚 *{curso.nombre}*

📊 *Calificación Final:* {calificacion}%"""
            if mencion:
                mensaje += f"\n🏆 *{mencion}*"

            mensaje += f"""

📜 Tu certificado digital está listo:
🔗 {media_url}

✅ Puedes verificar su autenticidad aquí:
{verificacion_url}

🔐 Código de verificación:
`{certificado.codigo_verificacion}`

¡Comparte tu logro con orgullo! 🌟"""

            resultado, modo_envio = _intentar_enviar_imagen_diploma(
                estudiante,
                certificado,
                caption=mensaje,
                media_url=media_url,
                pausa_inicial=0,
            )

        if resultado.get('success'):
            certificado.enviado_whatsapp = True
            certificado.fecha_envio = timezone.now()
            certificado.save(update_fields=['enviado_whatsapp', 'fecha_envio'])
            logger.info(
                "✅ Certificado %s enviado a %s (modo=%s, template_diploma=%s)",
                certificado.codigo_verificacion,
                estudiante.telefono,
                modo_envio,
                bool(sid),
            )
            return True

        logger.error(f"❌ Error enviando certificado: {resultado.get('response')}")
        return False

    except Exception as e:
        logger.error(f"❌ Error enviando certificado {certificado.codigo_verificacion}: {e}", exc_info=True)
        return False


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_whatsapp_respuesta` — `portal/utils.py:55`

```python
# portal/utils.py:55
def enviar_whatsapp_respuesta(telefono_destino, mensaje):
    """
    Envía un mensaje WhatsApp usando las credenciales Twilio del proyecto.
    telefono_destino debe estar en formato: 573XXXXXXXXX.
    """
    try:
        from twilio.rest import Client

        whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', None) or getattr(
            settings,
            'TWILIO_WHATSAPP_NUMBER',
            '',
        )
        whatsapp_from = str(whatsapp_from).replace('whatsapp:', '').strip()

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=f'whatsapp:{whatsapp_from}',
            to=f'whatsapp:+{limpiar_numero_whatsapp(telefono_destino)}',
            body=mensaje,
        )
        return True
    except Exception as e:
        print(f'Error enviando WhatsApp: {e}')
        return False
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_balance_gei_whatsapp` — `formulario/whatsapp_gei.py:1`

```python
# formulario/whatsapp_gei.py:1
"""Envío del balance GEI por WhatsApp."""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_balance_gei_whatsapp(ficha, estudiante=None) -> bool:
    """
    Persiste resultado, arma mensaje y envía por Twilio.
    Returns True si se envió, False si no había teléfono o está deshabilitado.
    """
    if not getattr(settings, "GEI_RESULTADO_WHATSAPP_ENABLED", True):
        return False

    est = estudiante or ficha.estudiante
    tel = (getattr(est, "telefono", None) or "").strip()
    if not tel:
        logger.warning("Sin teléfono para balance GEI estudiante_id=%s", getattr(est, "pk", "?"))
        return False

    from formulario.calculadora import generar_mensaje_resultado_whatsapp, persistir_resultado_gei

    try:
        persistir_resultado_gei(ficha)
        texto = generar_mensaje_resultado_whatsapp(ficha)
        if not tel.startswith("+"):
            tel = f"+{tel}"
        from core.utils import enviar_whatsapp_twilio

        enviar_whatsapp_twilio(tel, texto)
        return True
    except Exception as e:
        logger.exception("Error enviando balance GEI por WhatsApp: %s", e)
        return False
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_mensaje_motivacional` — `core/seguimiento_proactivo.py:46`

```python
# core/seguimiento_proactivo.py:46
def enviar_mensaje_motivacional(estudiante: Estudiante, razon: str = "inactividad"):
    """
    Envía mensaje motivacional personalizado
    
    Args:
        estudiante: Objeto Estudiante
        razon: Razón del mensaje ("inactividad", "progreso_lento", etc.)
    """
    try:
        # Generar mensaje con agente motivador
        agente = AgenteMotivador(estudiante)
        
        contexto_map = {
            "inactividad": f"El estudiante lleva varios días sin estudiar.",
            "progreso_lento": f"El estudiante avanza lento en su curso.",
            "modulo_abandonado": f"El estudiante dejó un módulo a la mitad."
        }
        
        mensaje = agente.generar_mensaje_motivacional(
            contexto_especifico=contexto_map.get(razon, "")
        )
        
        # Agregar llamado a la acción
        mensaje += "\n\n📚 Escribe 'continuar' para retomar tu curso."
        
        # Enviar mensaje
        resultado = enviar_whatsapp_twilio(
            telefono=estudiante.telefono,
            texto=mensaje
        )
        
        logger.info(f"✅ Mensaje motivacional enviado a {estudiante.nombre} ({razon})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando motivación a {estudiante.nombre}: {e}")
        return False


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ejecutar_seguimiento_proactivo` — `core/seguimiento_proactivo.py:85`

```python
# core/seguimiento_proactivo.py:85
def ejecutar_seguimiento_proactivo():
    """
    Función principal para ejecutar seguimiento automático
    Se puede llamar desde un CRON job o tarea programada
    """
    logger.info("🔄 Iniciando seguimiento proactivo...")
    
    # Detectar inactivos de 3 días
    inactivos_3d = detectar_estudiantes_inactivos(dias_inactividad=3)
    logger.info(f"📊 Estudiantes inactivos (3 días): {inactivos_3d.count()}")
    
    mensajes_enviados = 0
    
    for estudiante in inactivos_3d[:10]:  # Limitar a 10 por ejecución
        if enviar_mensaje_motivacional(estudiante, razon="inactividad"):
            mensajes_enviados += 1
    
    logger.info(f"✅ Seguimiento completado. Mensajes enviados: {mensajes_enviados}")
    return mensajes_enviados
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_previo_whatsapp` — `core/certificado_presencial_service.py:77`

```python
# core/certificado_presencial_service.py:77
def enviar_previo_whatsapp(
    estudiante: Estudiante,
    curso: Curso,
    *,
    texto_libre: str | None = None,
    twilio_content_sid: str | None = None,
) -> dict:
    """Aviso previo al diploma. Fuera de ventana 24 h use twilio_content_sid (plantilla aprobada)."""
    from core.enviar_plantillas import enviar_plantilla_twilio
    from core.utils import enviar_whatsapp_twilio

    sid = (twilio_content_sid or '').strip()
    if sid:
        return enviar_plantilla_twilio(
            estudiante.telefono,
            sid,
            variables={
                '1': estudiante.nombre or 'estudiante',
                '2': curso.nombre or 'curso',
            },
        )

    texto = (texto_libre or '').strip()
    if not texto:
        return {'success': True, 'skipped': True}

    cuerpo = texto.replace('{nombre}', estudiante.nombre or 'Estudiante')
    cuerpo = cuerpo.replace('{cedula}', estudiante.cedula or '')
    cuerpo = cuerpo.replace('{curso}', curso.nombre or '')
    return enviar_whatsapp_twilio(telefono=estudiante.telefono, texto=cuerpo)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_enviar_plantilla_twilio_cert` — `core/certificado_presencial_service.py:461`

```python
# core/certificado_presencial_service.py:461
def _enviar_plantilla_twilio_cert(telefono: str, content_sid: str, variables: dict) -> dict:
    """Wrapper testeable para enviar plantilla inicial (import perezoso de Twilio)."""
    from core.enviar_plantillas import enviar_plantilla_twilio

    return enviar_plantilla_twilio(telefono, content_sid, variables=variables)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_plantilla_inicial_certificado` — `core/certificado_presencial_service.py:468`

```python
# core/certificado_presencial_service.py:468
def enviar_plantilla_inicial_certificado(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
    *,
    twilio_content_sid_inicial: str,
    emitir_certificado: bool = True,
    calificacion: float = 100.0,
    regenerar_si_existe: bool = False,
    plantilla: PlantillaCertificado | None = None,
    permitir_otro_cliente: bool = True,
    cerrar_avance: bool = False,
) -> dict:
    """
    Flujo presencial recomendado SIN tocar la automatización de cursos:
      1. Emite el certificado (si aplica).
      2. Envía una plantilla Twilio inicial pidiendo que respondan *OK* o un número.
      3. Marca el certificado como pendiente en contexto_temporal.

    Cuando el estudiante responde OK/número, el webhook libera el certificado
    (la ventana de 24 h ya quedó abierta). NO usa 'listo' para no chocar con cursos.
    Si cerrar_avance y está en penúltimo/último módulo, el curso se cierra al entregar.
    """
    from django.utils import timezone

    sid = (twilio_content_sid_inicial or '').strip()
    if not sid:
        return {'errores': 0, 'sin_plantilla': True}

    estudiantes = Estudiante.objects.filter(pk__in=estudiante_ids, activo=True)
    if not permitir_otro_cliente:
        estudiantes = estudiantes.filter(cliente_id=curso.cliente_id)

    resumen = {
        'plantillas_enviadas': 0,
        'creados': 0,
        'existentes': 0,
        'regenerados': 0,
        'pendientes': 0,
        'omitidos': 0,
        'errores': 0,
    }

    for est in estudiantes:
        try:
            cert = None
            if emitir_certificado:
                cert, estado = crear_certificado_presencial(
                    est,
                    curso,
                    calificacion=calificacion,
                    regenerar_si_existe=regenerar_si_existe,
                    generar_archivo=True,
                    plantilla=plantilla,
                    permitir_otro_cliente=permitir_otro_cliente,
                )
                if estado == 'creado':
                    resumen['creados'] += 1
                elif estado == 'existente':
                    resumen['existentes'] += 1
                elif estado == 'regenerado':
                    resumen['regenerados'] += 1
                elif estado in ('error', 'error_generar', 'error_cliente'):
                    resumen['errores'] += 1
                    continue
            else:
                cert = Certificado.objects.filter(
                    estudiante=est, curso=curso, emitido=True,
                ).first()
                if not cert:
                    resumen['omitidos'] += 1
                    continue

            res = _enviar_plantilla_twilio_cert(
                est.telefono,
                sid,
                {
                    '1': est.nombre or 'estudiante',
                    '2': curso.nombre or 'curso',
                },
            )
            if not res.get('success'):
                resumen['errores'] += 1
                continue
            resumen['plantillas_enviadas'] += 1

            marcar_cert_envio_pendiente(
                est, cert, curso, cerrar_avance=cerrar_avance,
            )
            resumen['pendientes'] += 1
        except Exception:
            resumen['errores'] += 1

    return resumen


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_whatsapp_certificados_existentes` — `core/certificado_presencial_service.py:563`

```python
# core/certificado_presencial_service.py:563
@transaction.atomic
def enviar_whatsapp_certificados_existentes(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
    *,
    mensaje_previo: str | None = None,
    twilio_content_sid_media: str | None = None,
    media_var_index: str = '1',
    twilio_content_sid_previo: str | None = None,
    twilio_content_sid_diploma: str | None = None,
    permitir_otro_cliente: bool = True,
    cerrar_avance: bool = False,
) -> dict:
    """Reenvía por WhatsApp certificados ya emitidos (sin regenerar PDF)."""
    enviados = errores = omitidos = previos = 0
    sid_media = (twilio_content_sid_media or '').strip()
    sid_previo = (twilio_content_sid_previo or '').strip()
    sid_diploma = (twilio_content_sid_diploma or '').strip()
    texto_previo = (mensaje_previo or '').strip()

    qs = Certificado.objects.filter(
        curso=curso,
        estudiante_id__in=estudiante_ids,
        emitido=True,
    ).select_related('estudiante')
    if not permitir_otro_cliente:
        qs = qs.filter(estudiante__cliente_id=curso.cliente_id)

    for cert in qs:
        est = cert.estudiante
        try:
            # Plantilla con imagen = un solo mensaje, sin previo ni ventana.
            if not sid_media and (sid_previo or texto_previo):
                ok_prev = enviar_previo_whatsapp(
                    est,
                    curso,
                    texto_libre=texto_previo if not sid_previo else None,
                    twilio_content_sid=sid_previo or None,
                )
                if ok_prev.get('success'):
                    previos += 1
                    marcar_cert_envio_pendiente(
                        est, cert, curso, cerrar_avance=cerrar_avance,
                    )
                    continue
                errores += 1
                continue

            if enviar_certificado_whatsapp(
                cert,
                twilio_content_sid_media=sid_media or None,
                media_var_index=media_var_index,
                twilio_content_sid=sid_diploma or None,
                tras_plantilla_previo=bool(sid_previo or texto_previo),
            ):
                enviados += 1
                if cerrar_avance:
                    cerrar_curso_si_tramo_final(est, curso)
            else:
                errores += 1
        except Exception:
            errores += 1

    total_sel = len(set(estudiante_ids))
    omitidos = max(0, total_sel - enviados - errores)
    return {
        'mensajes_previos': previos,
        'enviados': enviados,
        'errores': errores,
        'omitidos': omitidos,
    }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_texto_sandbox` — `core/sandbox_menu.py:495`

```python
# core/sandbox_menu.py:495
def enviar_texto_sandbox(telefono_usuario: str, from_number: str, texto: str, *, agente: str = 'sandbox_menu') -> dict:
    from core.sandbox_canal import enviar_sandbox

    return enviar_sandbox(
        telefono_usuario,
        texto,
        from_number=from_number,
        canal_evento='whatsapp_sandbox',
        agente_evento=agente,
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_menu_sandbox` — `core/sandbox_menu.py:570`

```python
# core/sandbox_menu.py:570
def enviar_menu_sandbox(telefono_usuario: str, from_number: str) -> dict:
    from core.sandbox_canal import enviar_meta_botones, sandbox_via_meta

    if ofrecer_cursos_en_curso(telefono_usuario, from_number):
        return {'success': True, 'mensaje_id': None, 'response': 'cursos_en_curso'}
    plan = resolver_plan(telefono_usuario)
    if not plan.activo:
        return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_SIN_PLAN, agente='sandbox_plan')
    botones = []
    if plan.incluye_cursos:
        botones.append(('formacion', 'Formación'))
    if plan.incluye_asesor:
        botones.append(('asesoria', 'Asesoría'))
    texto = texto_menu_plan(plan)
    if sandbox_via_meta():
        return enviar_meta_botones(
            telefono_usuario,
            texto,
            botones,
            agente_evento='sandbox_menu',
        )
    palabras = ' o '.join(f"*{titulo.lower()}*" for _, titulo in botones)
    return enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        f"{texto}\n\nEscriba {palabras}.",
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_catalogo_formacion` — `core/sandbox_menu.py:599`

```python
# core/sandbox_menu.py:599
def enviar_catalogo_formacion(telefono_usuario: str, from_number: str) -> None:
    """Carrusel con los cursos generales del menú. Ver curso inscribe. Más información manda la ficha."""
    from core.cursos_generales import paginas_carrusel, tarjetas_catalogo
    from core.sandbox_canal import enviar_meta_botones, enviar_meta_carrusel, sandbox_via_meta

    if ofrecer_cursos_en_curso(telefono_usuario, from_number):
        return

    tarjetas = tarjetas_catalogo()
    cuerpo = (
        "Deslice los cursos de eki. "
        "*Ver curso* lo inscribe en ese programa. "
        "*Más información* le manda la ficha."
    )
    if not tarjetas:
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            "Aún no hay cursos de formación publicados.\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if sandbox_via_meta() and len(tarjetas) >= 2:
        fallo = None
        for i, pagina in enumerate(paginas_carrusel(tarjetas)):
            intro = cuerpo if i == 0 else "Siguen más cursos. Deslice."
            resultado = enviar_meta_carrusel(
                telefono_usuario,
                intro,
                pagina,
                agente_evento='sandbox_formacion',
            )
            if not resultado.get('success'):
                fallo = resultado.get('response')
                break
        if fallo is None:
            return
        logger.warning('sandbox_carrusel_fallback %s', fallo)
    if sandbox_via_meta() and len(tarjetas) == 1:
        tarjeta = tarjetas[0]
        enviar_meta_botones(
            telefono_usuario,
            tarjeta['body'],
            tarjeta['botones'],
            agente_evento='sandbox_formacion',
        )
        return
    lineas = [cuerpo, '']
    for tarjeta in tarjetas:
        ver = tarjeta['botones'][0][0]
        lineas.append(f"{tarjeta['body']}\nEscriba {ver} para empezar.")
    enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        '\n\n'.join(lineas),
        agente='sandbox_formacion',
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `responder_catalogo_general` — `core/sandbox_menu.py:658`

```python
# core/sandbox_menu.py:658
def responder_catalogo_general(telefono_usuario: str, from_number: str, body: str) -> None:
    from core.cursos_generales import inscribir_en_catalogo, item_catalogo, payload_catalogo

    dato = payload_catalogo(body) or {}
    item = item_catalogo(dato.get('clave') or '')
    if item is None:
        enviar_catalogo_formacion(telefono_usuario, from_number)
        return
    if dato.get('accion') == 'info':
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{item['nombre']}*\n{item['resumen']}\n\n{item['url']}\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    resultado = inscribir_en_catalogo(telefono_usuario, item['clave'])
    if resultado.get('error') == 'sin_plan_cursos':
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            TEXTO_PLAN_SIN_CURSOS if resolver_plan(telefono_usuario).activo else TEXTO_SIN_PLAN,
            agente='sandbox_plan',
        )
        return
    if resultado.get('error') == 'cupo_mes':
        cupo = resultado.get('cursos_mes') or 1
        cuantos = 'uno por mes' if cupo == 1 else f'{cupo} por mes'
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"Este mes ya eligió *{resultado.get('nombre_activo') or 'un curso'}*.\n\n"
            f"Su plan incluye cursos {cuantos} (de eki o de su organización). "
            "El próximo mes puede escoger otro.\n\n"
            "Escriba *listo* para seguir el que ya tiene.\n\n"
            "_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    if not resultado.get('ok'):
        enviar_texto_sandbox(
            telefono_usuario,
            from_number,
            f"*{item['nombre']}* todavía no está publicado en esta línea.\n\n"
            f"Puede ver la ficha:\n{item['url']}\n\n_*menu* para volver._",
            agente='sandbox_formacion',
        )
        return
    sesion = _get_or_create_sesion(telefono_usuario)
    _set_modo(sesion, MODO_CURSOS)
    enviar_texto_sandbox(
        telefono_usuario,
        from_number,
        f"Quedó en *{resultado['nombre']}*.\n\n"
        "Escriba *listo* para empezar. No se borra el avance de sus otros cursos.\n\n"
        "_*menu* para volver._",
        agente='sandbox_formacion',
    )


FILAS_AGENTES = [
    ('nat', 'Agrónomo Nat', 'Cultivo, plagas y campo'),
    ('coach', 'Coach', 'Hábitos y motivación'),
    ('profe', 'Profe IA', 'IA fácil para el campo'),
    ('ventas', 'Ventas', 'Clientes, precio y cierre'),
]


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `texto_lista_agentes` — `core/sandbox_menu.py:726`

```python
# core/sandbox_menu.py:726
def texto_lista_agentes(tope: int) -> str:
    cupo = f"Tiene hasta {tope} preguntas este mes.\n\n" if tope > 0 else ''
    return (
        "¿Con qué experto quiere hablar? Elija un agente en la lista; "
        "cada uno recuerda la conversación.\n\n"
        "También puede escribir su pregunta y lo llevamos al agente que corresponde.\n\n"
        f"{cupo}"
        "_*reiniciar* = memoria nueva · *menu* = menú principal._"
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_menu_agentes` — `core/sandbox_menu.py:737`

```python
# core/sandbox_menu.py:737
def enviar_menu_agentes(telefono_usuario: str, from_number: str) -> dict:
    from core.sandbox_agentes import _tope_asesor_mes
    from core.sandbox_canal import enviar_meta_lista, sandbox_via_meta

    if not sandbox_via_meta():
        return enviar_texto_sandbox(telefono_usuario, from_number, TEXTO_AGENTES, agente='sandbox_agentes')
    return enviar_meta_lista(
        telefono_usuario,
        texto_lista_agentes(_tope_asesor_mes(telefono_usuario)),
        'Ver agentes',
        FILAS_AGENTES,
        texto_respaldo=TEXTO_AGENTES,
        agente_evento='sandbox_agentes',
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_certificados_seleccion` — `core/certificado_presencial_service.py:636`

```python
# core/certificado_presencial_service.py:636
def enviar_certificados_seleccion(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
    *,
    mensaje_previo: str | None = None,
    twilio_content_sid_media: str | None = None,
    media_var_index: str = '1',
    twilio_content_sid_previo: str | None = None,
    twilio_content_sid_diploma: str | None = None,
    emitir_certificado: bool = True,
    enviar_whatsapp_certificado: bool = True,
    calificacion: float = 100.0,
    regenerar_si_existe: bool = False,
    plantilla: PlantillaCertificado | None = None,
    permitir_otro_cliente: bool = True,
    cerrar_avance: bool = False,
) -> dict:
    """
    Flujo tipo campaña + certificado para los marcados.
    No toca onboarding ni cursos distintos al del certificado.

    Si cerrar_avance=True y el estudiante está en el penúltimo o último módulo
    de *este* curso, el progreso se cierra cuando el diploma llega (tras respuesta
    o envío directo).

    Modo ideal: twilio_content_sid_media → plantilla aprobada con imagen del
    certificado en el header (un solo mensaje, sin previo ni ventana de 24 h).
    Alternativa: previo + imagen de sesión (twilio_content_sid_previo/diploma).
    """
    estudiantes = Estudiante.objects.filter(pk__in=estudiante_ids, activo=True)
    if not permitir_otro_cliente:
        estudiantes = estudiantes.filter(cliente_id=curso.cliente_id)

    resumen = {
        'mensajes_previos': 0,
        'creados': 0,
        'existentes': 0,
        'regenerados': 0,
        'certificados_enviados': 0,
        'pendientes_respuesta': 0,
        'cursos_cerrados': 0,
        'omitidos': 0,
        'errores': 0,
    }

    sid_media = (twilio_content_sid_media or '').strip()
    sid_previo = (twilio_content_sid_previo or '').strip()
    sid_diploma = (twilio_content_sid_diploma or '').strip()
    texto_previo = (mensaje_previo or '').strip()
    # Plantilla con imagen = un solo mensaje; no se usa el previo.
    usar_previo = bool(not sid_media and (sid_previo or texto_previo))

    for est in estudiantes:
        try:
            cert = None
            estado = None
            if emitir_certificado:
                cert, estado = crear_certificado_presencial(
                    est,
                    curso,
                    calificacion=calificacion,
                    regenerar_si_existe=regenerar_si_existe,
                    generar_archivo=True,
                    plantilla=plantilla,
                    permitir_otro_cliente=permitir_otro_cliente,
                )
                if estado == 'creado':
                    resumen['creados'] += 1
                elif estado == 'existente':
                    resumen['existentes'] += 1
                elif estado == 'regenerado':
                    resumen['regenerados'] += 1
                elif estado in ('error', 'error_generar', 'error_cliente'):
                    resumen['errores'] += 1
                    continue
            else:
                cert = Certificado.objects.filter(
                    estudiante=est, curso=curso, emitido=True,
                ).first()
                if not cert:
                    resumen['omitidos'] += 1
                    continue

            if usar_previo:
                ok_prev = enviar_previo_whatsapp(
                    est,
                    curso,
                    texto_libre=texto_previo if not sid_previo else None,
                    twilio_content_sid=sid_previo or None,
                )
                if ok_prev.get('success'):
                    resumen['mensajes_previos'] += 1
                else:
                    resumen['errores'] += 1
                    continue

                if enviar_whatsapp_certificado and cert and cert.emitido:
                    marcar_cert_envio_pendiente(
                        est, cert, curso, cerrar_avance=cerrar_avance,
                    )
                    if cert.enviado_whatsapp:
                        cert.enviado_whatsapp = False
                        cert.fecha_envio = None
                        cert.save(update_fields=['enviado_whatsapp', 'fecha_envio'])
                    resumen['pendientes_respuesta'] += 1
                continue

            if enviar_whatsapp_certificado and cert and cert.emitido:
                if enviar_certificado_whatsapp(
                    cert,
                    twilio_content_sid_media=sid_media or None,
                    media_var_index=media_var_index,
                    twilio_content_sid=sid_diploma or None,
                    tras_plantilla_previo=usar_previo,
                ):
                    resumen['certificados_enviados'] += 1
                    if cerrar_avance:
                        estado_cierre = cerrar_curso_si_tramo_final(est, curso)
                        if estado_cierre == 'cerrado':
                            resumen['cursos_cerrados'] += 1
                else:
                    resumen['errores'] += 1
            elif enviar_whatsapp_certificado and emitir_certificado:
                resumen['errores'] += 1
        except Exception:
            resumen['errores'] += 1

    return resumen
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `bot_comercial_salida` — `core/bot_comercial/webhook.py:1246`

```python
# core/bot_comercial/webhook.py:1246
    try:
        resultado_envio = enviar_whatsapp_twilio(
            telefono_limpio,
            texto_respuesta,
            from_number=from_number_respuesta,
        )
        if not resultado_envio.get('success'):
            raise RuntimeError(str(resultado_envio.get('response') or 'Error enviando por Twilio'))

        try:
            from core.eventos_ia import emit_mensaje_enviado

            emit_mensaje_enviado(
                telefono=telefono_limpio,
                texto=texto_respuesta,
                mensaje_id=resultado_envio.get('mensaje_id'),
                cliente=cliente_nati,
                canal='whatsapp_comercial',
                agente='nati',
            )
        except Exception:
            pass

        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=texto_respuesta[:1500],
            mensaje_id=resultado_envio.get('mensaje_id'),
            tipo='SENT',
            agente_usado='BOT_COMERCIAL',
        )
        # Fotos de productos recomendados (catálogo) — mensaje aparte por WhatsApp
        try:
            from core.bot_comercial.productos_media import (
                enviar_fotos_productos_whatsapp,
                fotos_productos_para_whatsapp,
            )

            fotos = fotos_productos_para_whatsapp(cliente_nati, texto_respuesta, limite=2)
            if fotos:
                envios = enviar_fotos_productos_whatsapp(
                    telefono_limpio,
                    fotos,
                    from_number=from_number_respuesta,
                )
                for item in envios:
                    ok = bool(item.get('success'))
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=(
                            f"[FOTO PRODUCTO] {item.get('nombre', '')}"
                            if ok
                            else f"[FOTO PRODUCTO FALLÓ] {item.get('nombre', '')}: {item.get('response', '')}"
                        )[:500],
                        mensaje_id=item.get('mensaje_id'),
                        tipo='SENT',
                        estado='SENT' if ok else 'FAILED',
                        agente_usado='BOT_COMERCIAL',
                    )
                    if not ok:
                        logger.warning(
                            'Nat foto producto no enviada | prod=%s | err=%s',
                            item.get('nombre'),
                            item.get('response'),
                        )
        except Exception:
            logger.exception('Nat: no se pudieron enviar fotos de producto')

        _actualizar_sesion_comercial(
            sesion=sesion_comercial,
            mensaje_usuario=msg_body or consulta,
            respuesta_bot=texto_respuesta,
        )
    except Exception as e:
        logger.error(f"❌ Error respondiendo bot comercial: {e}")

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.

