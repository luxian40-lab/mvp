# 02a — Transporte Twilio: core/utils.py

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `formatear_numero_whatsapp` — `core/utils.py:43`

```python
# core/utils.py:43
def formatear_numero_whatsapp(numero):
    """
    Recibe CUALQUIER formato de número y lo devuelve
    listo para que Twilio no tire el error 21212.
    """
    if not numero:
        return None
    numero = str(numero).strip()
    if numero.startswith('whatsapp:'):
        return numero
    if not numero.startswith('+'):
        numero = f"+{numero}"
    return f"whatsapp:{numero}"
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_whatsapp_twilio_content_template` — `core/utils.py:82`

```python
# core/utils.py:82
def enviar_whatsapp_twilio_content_template(telefono: str, content_sid: str, variables: dict) -> dict:
    """
    Enviar mensaje usando Twilio Content Template (aprobado por WhatsApp).
    
    Parámetros:
    - telefono: número en formato internacional, p.ej. '[REDACTADO]'
    - content_sid: Content SID del template aprobado (ej: 'HX123abc...')
    - variables: dict con las variables del template (ej: {'1': 'Juan', '2': 'Mensaje'})
    
    Retorna dict con keys: success(bool), mensaje_id (str|None), response (str).
    """
    log = None

    try:
        from core.sandbox_canal import sandbox_meta_activo, enviar_sandbox_template_fallback

        if sandbox_meta_activo():
            return enviar_sandbox_template_fallback(telefono, content_sid, variables)
    except Exception:
        logger.exception('sandbox_meta_intercept_content_template')

    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        # HARD-CODED para pruebas: usar siempre el número WhatsApp correcto
        twilio_number = '[REDACTADO]'
        
        if not account_sid or not auth_token:
            logger.error("Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}
        
        # Asegurar formato whatsapp:+57... para todos los destinatarios
        telefono_limpio = str(telefono).replace('whatsapp:', '').strip()
        if not telefono_limpio.startswith('+'):
            telefono_limpio = f'+{telefono_limpio}'
        telefono = f'whatsapp:{telefono_limpio}'
        
        logger.info(f"[TEMPLATE] Enviando a '{telefono}' con Content SID: {content_sid}")
        logger.debug(f"[VARIABLES] {variables}")
        logger.debug(f"FROM: '{twilio_number}' TO: '{telefono}'")
        
        # Crear cliente Twilio
        client = Client(account_sid, auth_token)
        
        # Construir mensaje de log legible
        mensaje_log = f"Template {content_sid}: {variables.get('2', 'Sin mensaje')}"
        
        # Guardar log preliminar
        log = WhatsappLog.objects.create(
            telefono=telefono.replace('whatsapp:', '').replace('+', ''),
            mensaje=mensaje_log,
            estado='PENDING',
            tipo='SENT',
            fecha=timezone.now()
        )
        
        # Enviar con Content Template (content_variables DEBE ser JSON string)
        import json
        msg_params = {
            'from_': twilio_number,
            'content_sid': content_sid,
            'to': telefono,
        }
        if variables:
            msg_params['content_variables'] = json.dumps(variables)

        try:
            message = client.messages.create(**msg_params)
        except Exception as send_err:
            err_txt = str(send_err)
            # Fallback para templates sin placeholders.
            if variables and 'Content Variables parameter is invalid' in err_txt:
                logger.warning(
                    f"Template {content_sid} rechazó variables; reintentando sin content_variables. "
                    f"Destino: {telefono}"
                )
                msg_params.pop('content_variables', None)
                message = client.messages.create(**msg_params)
            else:
                raise
        logger.info(f"Template enviado FROM: '{twilio_number}' TO: '{telefono}'")
        
        # Actualizar log con éxito
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.save()
        
        logger.info(f"Template enviado OK SID: {message.sid}")
        from core.salida_usuario import marcar_mensaje_salio
        marcar_mensaje_salio()
        return {'success': True, 'mensaje_id': message.sid, 'response': f'Sent: {message.status}'}
        
    except Exception as e:
        logger.error(f"Error al enviar template: {str(e)}")
        if log:
            log.estado = 'ERROR'
            log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
```

**Contrato**
- Entradas: `telefono`, `content_sid`, `variables` (dict de placeholders).
- Salidas: dict `success`, `mensaje_id`, `response`.
- Efectos: si `sandbox_meta_activo()`, delega a `enviar_sandbox_template_fallback` (Graph). Si no, `Client.messages.create` contra Twilio con `from_` fijo (número redactado en el código). Crea/actualiza `WhatsappLog` (PENDING→SENT o ERROR). Llama `marcar_mensaje_salio()`.
- Excepciones: el `except` exterior traga cualquier error, marca el log ERROR si existe y devuelve `success=False`. Un fallo de variables inválidas reintenta una vez sin `content_variables` y, si vuelve a fallar, cae en ese mismo `except`.


### `enviar_whatsapp_twilio` — `core/utils.py:184`

```python
# core/utils.py:184
def enviar_whatsapp_twilio(
    telefono: str,
    texto: str,
    mensaje_id_referencia: str = None,
    media_url: str = None,
    texto_log: str = None,
    from_number: str = None,
    canal_evento: str = 'whatsapp_edu',
    agente_evento: str = '',
) -> dict:
    """Enviar mensaje por Twilio WhatsApp API.

    Parámetros:
    - telefono: número en formato internacional, p.ej. '[REDACTADO]'
    - texto: cuerpo del mensaje a enviar
    - mensaje_id_referencia: ID del mensaje al que se responde (opcional)
    - media_url: URL del video o imagen (opcional)
    - texto_log: texto alternativo para guardar en log (para preservar marcadores internos)

    Retorna dict con keys: success(bool), mensaje_id (str|None), response (str).
    """
    log = None  # Inicializar log como None

    try:
        from core.sandbox_canal import sandbox_meta_activo, enviar_meta

        if sandbox_meta_activo():
            return enviar_meta(
                telefono,
                texto,
                media_url=media_url,
                canal_evento=canal_evento,
                agente_evento=agente_evento,
            )
    except Exception:
        logger.exception('sandbox_meta_intercept_twilio_send')

    try:
        from twilio.rest import Client
        from .response_templates import dividir_contenido_seguro

        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        # getattr(..., default) NO aplica si la setting existe y es None/''.
        default_from = (
            from_number
            or getattr(settings, 'TWILIO_PHONE_NUMBER', None)
            or getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
            or '[REDACTADO]'
        )
        twilio_number = formatear_numero_whatsapp(default_from)
        if not twilio_number:
            logger.error("TWILIO From inválido (PHONE/WHATSAPP vacíos)")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio From number not set'}
        twilio_number = str(twilio_number).strip()
        logger.info(f"[TWILIO] Account SID: {'...' + account_sid[-4:] if account_sid else None}")
        logger.info(f"[TWILIO] Auth Token: {'configured' if auth_token else 'MISSING'}")
        logger.info(f"[TWILIO] WhatsApp Number: '{twilio_number}'")

        if not account_sid or not auth_token:
            logger.error("Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}

        # Blindar el número destinatario contra error 21212
        telefono = formatear_numero_whatsapp(telefono)
        if not telefono:
            return {'success': False, 'mensaje_id': None, 'response': 'Invalid destination phone'}
        telefono = str(telefono).strip()

        # S3 URLs: usar URL pública directa (bucket tiene ACL public-read)
        # NO generar presigned URL — causa 63019 por redirect de región
        if media_url and 'amazonaws.com' in media_url:
            from .twilio_media import normalizar_media_url_s3, preparar_url_media_whatsapp

            media_url = normalizar_media_url_s3(media_url)
            try:
                media_url = preparar_url_media_whatsapp(media_url) or media_url
            except Exception as prep_err:
                logger.warning('[MEDIA] preparar_url falló: %s', prep_err)
            logger.info(f"[S3] URL pública directa: {media_url[:100]}...")
        elif media_url:
            from .twilio_media import preparar_url_media_whatsapp

            try:
                media_url = preparar_url_media_whatsapp(media_url) or media_url
            except Exception as prep_err:
                logger.warning('[MEDIA] preparar_url falló: %s', prep_err)

        # Crear cliente Twilio
        client = Client(account_sid, auth_token)

        # Guardar log preliminar - usar texto_log si existe, sino usar texto
        mensaje_para_log = texto_log if texto_log else texto
        try:
            log = WhatsappLog.objects.create(
                telefono=telefono.replace('whatsapp:', '').replace('+', ''),
                mensaje=mensaje_para_log,
                mensaje_id=mensaje_id_referencia,
                estado='PENDING',
                tipo='SENT',
                fecha=timezone.now()
            )
        except Exception as log_err:
            logger.warning(f"No se pudo crear log preliminar: {log_err}")
            log = None

        # Preparar parámetros del mensaje
        max_chars = int(getattr(settings, 'TWILIO_MAX_BODY_CHARS', 1500) or 1500)
        # Límite operativo seguro de Twilio WhatsApp: 1600 chars.
        if max_chars < 200 or max_chars > 1590:
            max_chars = 1500

        texto = str(texto or '').strip()
        chunks = dividir_contenido_seguro(texto, max_chars=max_chars) if texto else ['']

        if not chunks and not media_url:
            return {'success': False, 'mensaje_id': None, 'response': 'Empty body and no media'}

        sent_messages = []
        clean_url = str(media_url).strip() if media_url else None
        if clean_url:
            logger.info(f"[MEDIA] Enviando con multimedia: {clean_url}")

        from .response_templates import MENSAJE_CAPTION_SOLO_MEDIA as _caption_solo_media
        from .twilio_media import es_error_media_twilio

        status_cb = str(getattr(settings, 'TWILIO_STATUS_CALLBACK_URL', '') or '').strip()

        for idx, chunk in enumerate(chunks):
            chunk_eff = (chunk or '').strip()
            message_params = {
                'from_': twilio_number,
                'to': telefono,
            }
            # Adjunto sin texto: va solo, sin relleno genérico.
            if chunk_eff:
                message_params['body'] = chunk_eff
            if status_cb:
                message_params['status_callback'] = status_cb

            # Si hay multimedia, enviarla solo en el primer fragmento.
            if clean_url and idx == 0:
                message_params['media_url'] = [clean_url]

            try:
                message = client.messages.create(**message_params)
            except Exception as media_err:
                # 63019 / 63021 / 63005: reintento solo texto (nunca link S3 en el body).
                if es_error_media_twilio(media_err) and clean_url and idx == 0:
                    message_params.pop('media_url', None)
                    if not (message_params.get('body') or '').strip():
                        message_params['body'] = _caption_solo_media
                    logger.warning(
                        '[MEDIA] Twilio %s → reintento solo texto (sin URL S3) | %s',
                        media_err,
                        clean_url[:120],
                    )
                    message = client.messages.create(**message_params)
                else:
                    raise

            sent_messages.append(message)

        message = sent_messages[-1]
        logger.info(f"Enviado FROM: '{twilio_number}' TO: '{telefono}' ({len(sent_messages)} segmento(s))")

        if log:
            try:
                log.mensaje_id = message.sid
                log.estado = 'SENT'
                log.save()
            except Exception as log_err:
                logger.warning(f"No se pudo actualizar log: {log_err}")

        logger.info(f"TWILIO: Mensaje enviado a {telefono} - SID: {message.sid}")
        from core.salida_usuario import marcar_mensaje_salio
        marcar_mensaje_salio()

        try:
            from core.eventos_ia import emit_mensaje_enviado
            from core.ai_capabilities import resolver_ai_capability

            if resolver_ai_capability('eventos_ia'):
                emit_mensaje_enviado(
                    telefono=telefono,
                    texto=texto_log if texto_log else texto,
                    mensaje_id=message.sid,
                    canal=canal_evento,
                    agente=agente_evento,
                )
        except Exception:
            pass

        return {'success': True, 'mensaje_id': message.sid, 'response': 'Message sent'}
        
    except Exception as e:
        logger.error(f"Error enviando por Twilio: {str(e)}")
        if log:  # Solo actualizar si el log existe
            log.estado = 'ERROR'
            log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
```

**Contrato**
- Entradas: teléfono, texto, referencia opcional, `media_url`, `texto_log`, `from_number`, canal/agente de evento.
- Salidas: dict `success`, `mensaje_id` (SID del último segmento), `response`.
- Efectos: intercepta a `enviar_meta` si el contexto sandbox Meta está activo. Si no, Twilio `messages.create` por cada segmento (`TWILIO_MAX_BODY_CHARS`, tope 1590). `from` = argumento, o `TWILIO_PHONE_NUMBER`, o `TWILIO_WHATSAPP_NUMBER`, o número fijo redactado. Opcional `status_callback` = `TWILIO_STATUS_CALLBACK_URL`. Reintento sin media si el error es de media Twilio. Escribe `WhatsappLog`. Puede emitir `emit_mensaje_enviado`. `marcar_mensaje_salio()`.
- Excepciones: errores de log se tragan. El envío fallido cae en `except Exception`, pone estado ERROR y devuelve `success=False` (no propaga). `except Exception: pass` alrededor de la telemetría de eventos IA.


### `enviar_whatsapp` — `core/utils.py:387`

```python
# core/utils.py:387
def enviar_whatsapp(telefono: str, texto: str, mensaje_id_referencia: str = None) -> dict:
    """Enviar mensaje por WhatsApp Cloud API usando `requests` y registrar el intento.

    Parámetros:
    - telefono: número en formato internacional, p.ej. '57310...'
    - texto: cuerpo del mensaje
    - mensaje_id_referencia: ID del mensaje al que se responde (opcional)

    Retorna dict con keys: success(bool), mensaje_id (str|None), response (dict|str).
    """
    token = getattr(settings, 'WHATSAPP_TOKEN', None)
    phone_id = getattr(settings, 'WHATSAPP_PHONE_ID', None)
    api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v19.0')

    if not token or not phone_id:
        # No configurado
        return {'success': False, 'mensaje_id': None, 'response': 'Credentials not set'}

    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': telefono,
        'type': 'text',
        'text': {'body': texto}
    }

    # Guardamos un log preliminar (estado=PENDING, tipo=SENT para salida)
    log = WhatsappLog.objects.create(
        telefono=telefono,
        mensaje=texto,
        mensaje_id=mensaje_id_referencia,  # Referencia al mensaje original
        estado='PENDING',
        tipo='SENT',
        fecha=timezone.now()
    )

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        try:
            data = resp.json()
        except Exception:
            data = {'raw': resp.text}

        if resp.status_code in (200, 201) and 'messages' in data:
            mensaje_id = data['messages'][0].get('id')
            log.mensaje_id = mensaje_id
            log.estado = 'SENT'
            log.save()
            from core.salida_usuario import marcar_mensaje_salio
            marcar_mensaje_salio()
            return {'success': True, 'mensaje_id': mensaje_id, 'response': data}
        else:
            # Error desde la API
            err = data.get('error', data)
            log.estado = 'ERROR'
            log.save()
            return {'success': False, 'mensaje_id': None, 'response': err}

    except Exception as e:
        # Error de conexión u otra excepción
        log.estado = 'ERROR'
        log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
```

**Contrato**
- Entradas: teléfono, texto, `mensaje_id_referencia` opcional.
- Salidas: dict `success`, `mensaje_id` (wamid), `response`.
- Efectos: POST síncrono a `graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_ID}/messages` con timeout 10s. Credenciales globales `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_ID`. Crea `WhatsappLog` PENDING y lo pasa a SENT o ERROR. No envía plantilla. No reintenta 429/5xx.
- Excepciones: `except Exception` de red devuelve `success=False`. No propaga.

