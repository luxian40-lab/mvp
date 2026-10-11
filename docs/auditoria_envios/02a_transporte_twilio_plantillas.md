# 02a — Plantillas Twilio, whatsapp_service y segmentación

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `whatsapp_service` — `core/whatsapp_service.py:1`

```python
# core/whatsapp_service.py:1

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_video_whatsapp` — `core/whatsapp_service.py:2`

```python
# core/whatsapp_service.py:2
def enviar_video_whatsapp(to, video_url):
    pass


# ====================================================
# 🚀 FUNCIÓN MAESTRA: Enviar Content Templates de Twilio
# ====================================================
import json
import logging
from twilio.rest import Client
from django.conf import settings
from .models_extras import ArchivoModulo
from .models import WhatsappLog
from django.utils import timezone

logger = logging.getLogger(__name__)

# ====================================================
# Content SIDs de Twilio (Plantillas Aprobadas)
# ====================================================
TWILIO_CONTENT_SIDS = {
    'habeas_data': 'HX[REDACTADO]',
    'confirmar_datos': 'HX[REDACTADO]',
    'confirmar_datos_v2': 'HX[REDACTADO]',
    'menu_principal': 'HX[REDACTADO]',
    'listadocursos1': 'HX[REDACTADO]',
    'listadocursos2': 'HX[REDACTADO]',
    'listadocursos3': 'HX[REDACTADO]',
    'listadocursos4': 'HX[REDACTADO]',
    'continuar_modulo': 'HX[REDACTADO]',
}


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_template_twilio` — `core/whatsapp_service.py:35`

```python
# core/whatsapp_service.py:35
def enviar_template_twilio(telefono, content_sid, variables=None):
    """
    Función maestra para enviar mensajes con Content Templates de Twilio.
    
    Args:
        telefono (str): Número destino (ej: [REDACTADO])
        content_sid (str): El Content SID del template (HX...)
        variables (dict): Variables del template (ej: {'1': 'Juan', '2': 'CC 12345'})
    
    Returns:
        dict: {'success': bool, 'mensaje_id': str|None, 'response': str}
    """
    try:
        from core.sandbox_canal import sandbox_meta_activo, enviar_sandbox_template_fallback

        if sandbox_meta_activo():
            return enviar_sandbox_template_fallback(telefono, content_sid, variables)
    except Exception:
        logger.exception('sandbox_meta_intercept_template')

    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        twilio_number = '[REDACTADO]'
        
        if not account_sid or not auth_token:
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials missing'}
        
        # Formatear teléfono
        telefono_limpio = str(telefono).replace('whatsapp:', '').strip()
        if not telefono_limpio.startswith('+'):
            telefono_limpio = f'+{telefono_limpio}'
        destino = f'whatsapp:{telefono_limpio}'
        
        client = Client(account_sid, auth_token)
        
        msg_params = {
            'from_': twilio_number,
            'content_sid': content_sid,
            'to': destino,
        }
        
        if variables:
            msg_params['content_variables'] = json.dumps(variables)

        try:
            message = client.messages.create(**msg_params)
        except Exception as send_err:
            err_txt = str(send_err)
            # Algunos templates no esperan variables y Twilio rechaza content_variables.
            if variables and 'Content Variables parameter is invalid' in err_txt:
                logger.warning(
                    f"Template {content_sid} rechazó variables; reintentando sin content_variables. "
                    f"Destino: {destino}"
                )
                msg_params.pop('content_variables', None)
                message = client.messages.create(**msg_params)
            else:
                raise
        
        # Log
        WhatsappLog.objects.create(
            telefono=telefono_limpio.replace('+', ''),
            mensaje=f"[TEMPLATE:{content_sid}] vars={variables}",
            mensaje_id=message.sid,
            estado='SENT',
            tipo='SENT',
            fecha=timezone.now()
        )
        
        logger.info(f"✅ Template {content_sid} enviado a {destino}: {message.sid}")
        return {'success': True, 'mensaje_id': message.sid, 'response': f'Sent: {message.status}'}
        
    except Exception as e:
        logger.error(f"❌ Error enviando template: {e}")
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


```

**Contrato**
- Entradas: teléfono, content SID, variables opcionales.
- Salidas: dict `success`, `mensaje_id`, `response`.
- Efectos: mismo intercept sandbox que el content template de `utils`. `from_` fijo (redactado), no usa settings de número. `messages.create`. `WhatsappLog` solo en éxito (no hay fila PENDING). Reintento único sin variables si Twilio dice que son inválidas.
- Excepciones: cualquier otro error → `success=False`, no propaga.


### `_resolver_content_sid_habeas_data` — `core/whatsapp_service.py:113`

```python
# core/whatsapp_service.py:113
def _resolver_content_sid_habeas_data(cliente=None):
    """Resuelve el Content SID de Habeas Data con esta jerarquía:

    1. Plantilla Twilio del Cliente (`Cliente.content_sid_habeas_data_twilio`).
    2. Plantilla global editable desde admin (`ConfiguracionGlobal.content_sid_habeas_data_global`).
    3. Fallback histórico hardcoded (`TWILIO_CONTENT_SIDS['habeas_data']`).
    """
    sid_cliente = (getattr(cliente, 'content_sid_habeas_data_twilio', '') or '').strip()
    if sid_cliente:
        return sid_cliente
    try:
        from .models import ConfiguracionGlobal
        cfg = ConfiguracionGlobal.get_solo()
        sid_global = (cfg.content_sid_habeas_data_global or '').strip()
        if sid_global:
            return sid_global
    except Exception as e:
        logger.warning(f"⚠️ No se pudo leer ConfiguracionGlobal habeas data: {e}")
    return TWILIO_CONTENT_SIDS['habeas_data']


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_habeas_data` — `core/whatsapp_service.py:134`

```python
# core/whatsapp_service.py:134
def enviar_habeas_data(telefono, cliente=None):
    """Paso 1: Enviar mensaje de Habeas Data con botones [Acepto] [No acepto].

    Args:
        telefono: número destino.
        cliente: instancia opcional de `core.Cliente`. Si tiene
            `content_sid_habeas_data_twilio` se prioriza sobre la plantilla global.
    """
    content_sid = _resolver_content_sid_habeas_data(cliente=cliente)
    return enviar_template_twilio(telefono, content_sid)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_confirmacion_datos` — `core/whatsapp_service.py:146`

```python
# core/whatsapp_service.py:146
def enviar_confirmacion_datos(telefono, nombre, cedula, organizacion, edad=None, municipio=None):
    """Paso 2: Verificación exitosa — confirmar datos con 5 variables
    Template: 👤 Verificación Exitosa
    {{1}} = Nombre, {{2}} = Cédula, {{3}} = Empresa, {{4}} = Edad, {{5}} = Municipio
    """
    return enviar_template_twilio(
        telefono,
        TWILIO_CONTENT_SIDS['confirmar_datos_v2'],
        variables={
            '1': nombre or 'No registrado',
            '2': cedula or 'No registrada',
            '3': organizacion or 'eki',
            '4': str(edad) if edad else 'No registrada',
            '5': municipio or 'No registrado',
        }
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_menu_principal` — `core/whatsapp_service.py:164`

```python
# core/whatsapp_service.py:164
def enviar_menu_principal(telefono, nombre):
    """Paso 3: Menú principal con botones [Mis cursos] [Mis puntos] [Ayuda]"""
    return enviar_template_twilio(
        telefono,
        TWILIO_CONTENT_SIDS['menu_principal'],
        variables={'1': nombre}
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_lista_cursos` — `core/whatsapp_service.py:173`

```python
# core/whatsapp_service.py:173
def enviar_lista_cursos(telefono, estudiante):
    """
    Envía lista dinámica de cursos como texto plano (más confiable).
    Muestra progreso del estudiante en cada curso.
    El estudiante solo necesita escribir el número para seleccionar.
    """
    from .models import Curso, ProgresoEstudiante
    
    org = estudiante.cliente
    
    # Obtener TODOS los cursos activos del estudiante
    if org:
        cursos = Curso.objects.filter(
            cliente=org, activo=True
        ).order_by('orden', 'nombre')
    else:
        cursos = Curso.objects.filter(activo=True).order_by('orden', 'nombre')
    
    cursos_list = list(cursos)
    cantidad = len(cursos_list)
    
    if cantidad == 0:
        from .utils import enviar_whatsapp_twilio
        return enviar_whatsapp_twilio(
            telefono,
            "📚 No hay cursos disponibles en este momento. Escribe *menú* para volver."
        )
    
    # Agregar info de progreso a cada curso
    progresos = ProgresoEstudiante.objects.filter(
        estudiante=estudiante
    ).select_related('curso')
    progreso_map = {p.curso_id: p for p in progresos}
    
    nombre = estudiante.nombre or 'Estudiante'
    org_nombre = org.nombre if org else 'eki'
    
    msg = f"📚 *Cursos disponibles — {org_nombre}*\n"
    msg += f"Hola *{nombre}*, estos son tus cursos:\n\n"
    
    for idx, curso in enumerate(cursos_list, 1):
        emoji = curso.emoji or "📖"
        prog = progreso_map.get(curso.id)
        estado = ""
        if prog:
            if prog.completado:
                estado = " ✅ Completado"
            else:
                porcentaje = prog.porcentaje_avance()
                if porcentaje > 0:
                    estado = f" ⏳ {porcentaje}%"
                else:
                    estado = " 🆕"
        else:
            estado = " 🆕"
        
        msg += f"*{idx}.* {emoji} {curso.nombre}{estado}\n"
    
    msg += "👉 Escribe *tomar 1* para el primer curso\n"
    msg += "     Ejemplo: *tomar 1* o simplemente *1*\n\n"
    msg += "👉 Escribe *menú* para volver"
    
    from .utils import enviar_whatsapp_twilio
    return enviar_whatsapp_twilio(telefono, msg)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_mensaje_ventas` — `core/whatsapp_service.py:239`

```python
# core/whatsapp_service.py:239
def enviar_mensaje_ventas(telefono):
    """
    Fase 0: Mensaje para usuarios no registrados.
    Envía texto plano con opciones de menú (incl. 4 = carrusel programas demo).
    """
    msg = (
        "🚜 ¡Hola! Soy eki, la plataforma educativa por WhatsApp "
        "para el sector agrícola.\n\n"
        "Veo que tu número no está registrado en ninguna de nuestras "
        "capacitaciones actuales.\n\n"
        "¿En qué te podemos ayudar?\n\n"
        "1️⃣ 🏢 *eki para mi empresa*\n"
        "   Capacitar trabajadores con nosotros\n\n"
        "2️⃣ 🌐 *Visitar sitio web*\n"
        "   www.eki.com.co\n\n"
        "3️⃣ 🙋‍♂️ *Soy estudiante (Ayuda)*\n"
        "   Si cambiaste de número o necesitas ayuda\n\n"
        "4️⃣ 📚 *Ver programas (demo)*\n"
        "   Carrusel: ejemplos + demo *Tome las riendas*\n\n"
        "👉 Escribe el *número* de tu opción (1, 2, 3 o 4)"
    )
    
    from .utils import enviar_whatsapp_twilio
    return enviar_whatsapp_twilio(telefono, msg)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_gamificacion_visual` — `core/whatsapp_service.py:265`

```python
# core/whatsapp_service.py:265
def enviar_gamificacion_visual(telefono, estudiante):
    """
    Envía estado visual de gamificación al estudiante.
    Barra de progreso emoji + nivel + puntos.
    """
    from .gamificacion import PerfilGamificacion
    
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
    except PerfilGamificacion.DoesNotExist:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    
    # Generar barra de progreso
    barra = generar_barra_progreso_emoji(perfil.porcentaje_nivel())
    
    # Nombres de nivel temáticos del campo
    NOMBRES_NIVEL = {
        1: '🌱 Semilla', 2: '🌿 Brote', 3: '🌾 Sembrador',
        4: '🌻 Cultivador', 5: '🌳 Agricultor',
        6: '🚜 Tractorista', 7: '🏅 Capataz',
        8: '⭐ Mayordomo', 9: '👑 Hacendado',
        10: '🏆 Leyenda del Campo'
    }
    
    nombre_nivel = NOMBRES_NIVEL.get(perfil.nivel, f'Nivel {perfil.nivel}')
    
    msg = (
        f"¡Vas volando, *{estudiante.nombre}*! 🚀\n\n"
        f"\n\n"
        f"🏆 *Nivel:* {nombre_nivel}\n"
        f"⭐ *Puntos:* {perfil.puntos_totales} pts\n"
        f"🎯 *Avance:* {barra} {perfil.porcentaje_nivel()}%\n\n"
    )
    
    if perfil.puntos_para_siguiente_nivel() > 0:
        msg += f"📈 Faltan *{perfil.puntos_para_siguiente_nivel()} pts* para el siguiente nivel\n\n"
    
    msg += "¡Sigue así! 💪\n\n"
    msg += "Escribe *menú* para volver"
    
    from .utils import enviar_whatsapp_twilio
    return enviar_whatsapp_twilio(telefono, msg)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `generar_barra_progreso_emoji` — `core/whatsapp_service.py:309`

```python
# core/whatsapp_service.py:309
def generar_barra_progreso_emoji(porcentaje, longitud=10):
    """
    Genera una barra de progreso con emojis.
    
    Args:
        porcentaje (int): 0-100
        longitud (int): Cantidad total de bloques
    
    Returns:
        str: Ej. '🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜'
    """
    porcentaje = max(0, min(100, porcentaje))
    llenos = round((porcentaje / 100) * longitud)
    vacios = longitud - llenos
    return '🟩' * llenos + '⬜' * vacios

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_archivo_modulo_whatsapp` — `core/whatsapp_service.py:325`

```python
# core/whatsapp_service.py:325
def enviar_archivo_modulo_whatsapp(telefono, archivo_modulo, texto_extra=None):
    """
    Envía cualquier archivo de ArchivoModulo por WhatsApp usando Twilio.
    Args:
        telefono (str): Número destino en formato internacional (ej: [REDACTADO])
        archivo_modulo (ArchivoModulo): Instancia de ArchivoModulo
        texto_extra (str): Texto adicional a enviar junto con el archivo (opcional)
    Returns:
        dict: {'success': bool, 'mensaje_id': str|None, 'response': str}
    """
    url_envio = archivo_modulo.get_url_para_envio()
    if not url_envio:
        return {'success': False, 'mensaje_id': None, 'response': 'No hay URL pública para el archivo'}

    # Descripción según tipo
    tipo = archivo_modulo.get_tipo_display() if hasattr(archivo_modulo, 'get_tipo_display') else archivo_modulo.tipo
    titulo = archivo_modulo.titulo or ''
    descripcion = f"{tipo}: {titulo}"
    if texto_extra:
        descripcion = f"{descripcion}\n{texto_extra}"

    try:
        from core.sandbox_canal import sandbox_meta_activo, enviar_meta

        if sandbox_meta_activo():
            return enviar_meta(telefono, descripcion, media_url=url_envio, canal_evento='whatsapp_sandbox', agente_evento='sandbox_cursos')
    except Exception:
        logger.exception('sandbox_meta_intercept_archivo')

    # Preparar log preliminar
    log = WhatsappLog.objects.create(
        telefono=telefono.replace('whatsapp:', '').replace('+', ''),
        mensaje=descripcion,
        estado='PENDING',
        tipo='SENT',
        fecha=timezone.now()
    )

    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        whatsapp_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
        if not all([account_sid, auth_token, whatsapp_number]):
            raise ValueError("Faltan credenciales de Twilio en settings.py")

        # Formato correcto para Twilio
        to = telefono
        if not to.startswith('whatsapp:'):
            if not to.startswith('+'):
                to = f'+{to}'
            to = f'whatsapp:{to}'

        # Formatear número FROM correctamente (evitar doble whatsapp:)
        from_number = str(whatsapp_number).strip()
        if not from_number.startswith('whatsapp:'):
            if not from_number.startswith('+'):
                from_number = f'+{from_number}'
            from_number = f'whatsapp:{from_number}'

        client = Client(account_sid, auth_token)
        # Agregar status_callback para rastreo
        status_callback_url = getattr(settings, 'TWILIO_STATUS_CALLBACK', None)
        message_params = {
            'from_': from_number,
            'to': to,
            'body': descripcion,
            'media_url': [url_envio]
        }
        if status_callback_url:
            message_params['status_callback'] = status_callback_url

        message = client.messages.create(**message_params)
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.error_detalle = ''
        log.save()
        return {'success': True, 'mensaje_id': message.sid, 'response': 'Enviado'}
    except Exception as e:
        log.estado = 'ERROR'
        log.error_detalle = str(e)
        log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_plantillas` — `core/enviar_plantillas.py:1`

```python
# core/enviar_plantillas.py:1
"""
Sistema de envío de plantillas aprobadas de WhatsApp via Twilio
"""
from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_plantilla_twilio` — `core/enviar_plantillas.py:11`

```python
# core/enviar_plantillas.py:11
def enviar_plantilla_twilio(telefono: str, content_sid: str, variables: dict = None) -> dict:
    """
    Envía una plantilla aprobada de WhatsApp via Twilio.
    
    Args:
        telefono: Número en formato +57... (sin whatsapp:)
        content_sid: SID de la plantilla aprobada (ej: HX1234...)
        variables: Diccionario con variables de la plantilla (ej: {'1': 'Juan', '2': 'Plátano'})
    
    Returns:
        dict: {'success': bool, 'mensaje_id': str, 'response': str}
    
    Ejemplo:
        enviar_plantilla_twilio(
            telefono='[REDACTADO]',
            content_sid='HXa1b2c3d4...',
            variables={'1': 'Juan', '2': 'Plátano Hartón'}
        )
    """
    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN')
        # Misma regla que utils: PHONE vacío no debe dejar From en sandbox/None.
        twilio_number = (
            getattr(settings, 'TWILIO_PHONE_NUMBER', None)
            or getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
            or '[REDACTADO]'
        )
        twilio_number = str(twilio_number).strip()
        if not twilio_number.startswith('whatsapp:'):
            if not twilio_number.startswith('+'):
                twilio_number = f'+{twilio_number}'
            twilio_number = f'whatsapp:{twilio_number}'
        # Sandbox local no inicia conversación real a números CO.
        if '[REDACTADO]' in twilio_number:
            twilio_number = '[REDACTADO]'
        logger.info("TWILIO FROM (plantilla): %s", twilio_number)
        if not account_sid or not auth_token:
            return {'success': False, 'mensaje_id': None, 'response': 'Credenciales no configuradas'}
        
        # Crear cliente
        client = Client(account_sid, auth_token)
        
        # Asegurar formato whatsapp:+57...
        if not telefono.startswith('whatsapp:'):
            if not telefono.startswith('+'):
                telefono = f'+{telefono}'
            telefono = f'whatsapp:{telefono}'
        telefono = str(telefono).strip()
        
        # Preparar parámetros del mensaje
        message_params = {
            'from_': twilio_number,
            'to': telefono,
            'content_sid': content_sid
        }
        
        # Agregar variables si existen
        if variables:
            # Twilio espera formato: ContentVariables={"1": "valor1", "2": "valor2"}
            import json
            message_params['content_variables'] = json.dumps(variables)
        
        # Enviar mensaje con plantilla
        message = client.messages.create(**message_params)
        
        logger.info(f"✅ Plantilla enviada a {telefono} - SID: {message.sid}")
        
        return {
            'success': True,
            'mensaje_id': message.sid,
            'response': 'Template sent',
            'status': message.status
        }
        
    except Exception as e:
        logger.error(f"❌ Error enviando plantilla: {str(e)}")
        return {
            'success': False,
            'mensaje_id': None,
            'response': str(e)
        }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_campana_con_plantilla` — `core/enviar_plantillas.py:95`

```python
# core/enviar_plantillas.py:95
def enviar_campana_con_plantilla(campana_id: int) -> dict:
    """
    Envía una campaña usando plantilla aprobada a todos los destinatarios.
    
    Args:
        campana_id: ID de la campaña
    
    Returns:
        dict: Estadísticas del envío
    """
    from .models import Campana, EnvioLog
    
    try:
        campana = Campana.objects.get(id=campana_id)
        plantilla = campana.plantilla
        
        # Verificar que tenga Content SID (plantilla aprobada)
        if not plantilla.twilio_template_sid:
            return {
                'success': False,
                'error': 'La plantilla no tiene Content SID de Twilio configurado'
            }
        
        destinatarios = campana.destinatarios.all()
        if not destinatarios.exists():
            return {
                'success': False,
                'error': 'No hay destinatarios en la campaña'
            }
        
        enviados = 0
        fallidos = 0
        
        for estudiante in destinatarios:
            # Preparar variables de la plantilla
            variables = {
                '1': estudiante.nombre or 'Estudiante',
                '2': campana.nombre
            }
            
            # Enviar plantilla
            resultado = enviar_plantilla_twilio(
                telefono=estudiante.telefono,
                content_sid=plantilla.twilio_template_sid,
                variables=variables
            )
            
            # Crear registro de envío
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='ENVIADO' if resultado['success'] else 'ERROR',
                respuesta_api=resultado.get('response', '')[:500]
            )
            
            if resultado['success']:
                enviados += 1
            else:
                fallidos += 1
        
        return {
            'success': True,
            'total': destinatarios.count(),
            'enviados': enviados,
            'fallidos': fallidos
        }
        
    except Exception as e:
        logger.error(f"❌ Error en campaña: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `crear_template_twilio` — `core/enviar_plantillas.py:170`

```python
# core/enviar_plantillas.py:170
def crear_template_twilio(nombre: str, contenido: str, variables: list = None) -> dict:
    """
    Crea un Content Template en Twilio para WhatsApp.
    
    Args:
        nombre: Nombre único para el template (ej: 'saludo_bienvenida')
        contenido: Texto del mensaje con placeholders {{1}}, {{2}}, etc.
        variables: Lista de nombres de variables ['nombre', 'mensaje'] (opcional)
    
    Returns:
        dict: {'success': bool, 'content_sid': str, 'response': str}
    
    Ejemplo:
        crear_template_twilio(
            nombre='saludo_curso',
            contenido='Hola {{1}}, bienvenido al curso de {{2}}!',
            variables=['nombre', 'curso']
        )
    """
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token:
            return {'success': False, 'content_sid': None, 'response': 'Credenciales no configuradas'}
        
        client = Client(account_sid, auth_token)
        
        # Crear Content Template
        content = client.content.contents.create(
            friendly_name=nombre,
            language='es',
            types={
                'twilio/text': {
                    'body': contenido
                }
            }
        )
        
        logger.info(f"✅ Template creado: {content.sid}")
        
        return {
            'success': True,
            'content_sid': content.sid,
            'response': f'Template creado con SID: {content.sid}'
        }
        
    except Exception as e:
        logger.error(f"❌ Error al crear template: {str(e)}")
        return {
            'success': False,
            'content_sid': None,
            'response': str(e)
        }


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `listar_templates_twilio` — `core/enviar_plantillas.py:228`

```python
# core/enviar_plantillas.py:228
def listar_templates_twilio() -> list:
    """
    Lista todos los Content Templates de Twilio para la cuenta.
    
    Returns:
        list: Lista de dicts con información de templates
    """
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token:
            return []
        
        client = Client(account_sid, auth_token)
        
        templates = []
        for content in client.content.contents.list(limit=100):
            templates.append({
                'sid': content.sid,
                'friendly_name': content.friendly_name,
                'language': content.language,
                'date_created': content.date_created
            })
        
        return templates
        
    except Exception as e:
        logger.error(f"❌ Error al listar templates: {str(e)}")
        return []
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `twilio_transporte` — `core/views/twilio_transporte.py:1`

```python
# core/views/twilio_transporte.py:1
import logging

from django.conf import settings

from ..models import WhatsappLog
from ..response_templates import MENSAJE_CAPTION_SOLO_MEDIA as TWILIO_CAPTION_ADJUNTO

logger = logging.getLogger(__name__)

_TWILIO_STATUS_CALLBACKS = frozenset({
    'queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed', 'read',
})

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_twilio_post_plano` — `core/views/twilio_transporte.py:14`

```python
# core/views/twilio_transporte.py:14
def _twilio_post_plano(post_data) -> dict:
    if hasattr(post_data, 'keys'):
        return {k: post_data.get(k) for k in post_data.keys()}
    return dict(post_data)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_es_status_callback_twilio` — `core/views/twilio_transporte.py:19`

```python
# core/views/twilio_transporte.py:19
def _es_status_callback_twilio(post_data) -> bool:
    message_status = (post_data.get('MessageStatus') or post_data.get('SmsStatus') or '').lower()
    return bool(message_status and message_status in _TWILIO_STATUS_CALLBACKS)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_encolar_twilio_edu_si_async` — `core/views/twilio_transporte.py:23`

```python
# core/views/twilio_transporte.py:23
def _encolar_twilio_edu_si_async(post_data, *, reply_from_number: str | None = None) -> bool:
    """Encola webhook educativo en Celery si WEBHOOK_CELERY_ASYNC=true."""
    if not getattr(settings, 'WEBHOOK_CELERY_ASYNC', False):
        return False
    if _es_status_callback_twilio(post_data):
        return False
    from core.tasks import procesar_twilio_webhook_async

    plano = _twilio_post_plano(post_data)
    # Menú sandbox dual: el worker debe responder desde el mismo From.
    from_override = (reply_from_number or '').strip()
    if not from_override:
        try:
            from core.wa_reply_context import get_reply_from_override

            from_override = (get_reply_from_override() or '').strip()
        except Exception:
            from_override = ''
    if from_override:
        plano['_eki_reply_from'] = from_override

    procesar_twilio_webhook_async.delay(plano)
    logger.info("📤 Webhook educativo encolado en Celery | sid=%s", post_data.get('MessageSid', ''))
    return True

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_escape_twiml` — `core/views/twilio_transporte.py:48`

```python
# core/views/twilio_transporte.py:48
def _escape_twiml(text):
    """Escapa caracteres especiales para TwiML XML."""
    if not text:
        return text
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_reenviar_media_fallida_como_enlace` — `core/views/twilio_transporte.py:57`

```python
# core/views/twilio_transporte.py:57
def _reenviar_media_fallida_como_enlace(log, error_code: str = '') -> None:
    """
    Ante 63019/63021/63005: reintento automático del mismo MediaUrl (1–2 veces).
    No envía links S3 en el cuerpo. Si agota reintentos, queda estado fallido
    y el productor puede pedir *reenvía video*.
    """
    from ..media_entrega import reintentar_media_desde_log
    from ..twilio_media import es_error_media_twilio

    if not es_error_media_twilio(error_code):
        return
    ok = reintentar_media_desde_log(log, error_code)
    if not ok:
        logger.warning(
            '📎 Media undelivered/failed tras reintento(s) | sid=%s code=%s tel=%s',
            getattr(log, 'mensaje_id', ''),
            error_code,
            getattr(log, 'telefono', ''),
        )

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_registrar_estado_twilio_callback` — `core/views/twilio_transporte.py:77`

```python
# core/views/twilio_transporte.py:77
def _registrar_estado_twilio_callback(post_data):
    """
    Actualiza estado de WhatsappLog (SENT) con callbacks de Twilio.
    Permite métricas de entregado/abierto/fallido por mensaje.
    Ante 63019/63021/63005 solo registra el fallo (no envía links S3).
    """
    try:
        sid = (
            post_data.get('MessageSid')
            or post_data.get('SmsSid')
            or post_data.get('message_sid')
            or ''
        )
        status_raw = (
            post_data.get('MessageStatus')
            or post_data.get('SmsStatus')
            or post_data.get('status')
            or ''
        )
        status = str(status_raw).strip().upper()
        error_code = str(
            post_data.get('ErrorCode') or post_data.get('error_code') or ''
        ).strip()
        error_message = str(
            post_data.get('ErrorMessage') or post_data.get('error_message') or ''
        ).strip()

        if not sid or not status:
            return

        # Tomar el último envío con este SID para no tocar INCOMING.
        log = (
            WhatsappLog.objects.filter(mensaje_id=sid, tipo='SENT')
            .order_by('-fecha')
            .first()
        )
        if log:
            campos = []
            if log.estado != status:
                log.estado = status
                campos.append('estado')
            detalle = ' '.join(x for x in (error_code, error_message) if x).strip()
            if detalle and detalle != (log.error_detalle or '').strip():
                # Conservar marcador FALLBACK_ENLACE si ya existía.
                prev = log.error_detalle or ''
                if 'FALLBACK_ENLACE' in prev and 'FALLBACK_ENLACE' not in detalle:
                    detalle = f'{detalle} | FALLBACK_ENLACE'
                log.error_detalle = detalle[:2000]
                campos.append('error_detalle')
            if campos:
                log.save(update_fields=campos)
            if status in ('UNDELIVERED', 'FAILED') and error_code:
                _reenviar_media_fallida_como_enlace(log, error_code)
            # Telemetría entrega media (Centro de Éxito).
            try:
                from core.models import Estudiante, EstudianteEventoAprendizaje
                from core.telemetria import registrar_evento
                from core.utils_telefono import variantes_telefono

                est = log.estudiante
                if est is None and log.telefono:
                    for v in variantes_telefono(log.telefono):
                        est = Estudiante.objects.filter(telefono=v).first()
                        if est:
                            break
                if est:
                    tipo_ev = (
                        EstudianteEventoAprendizaje.TIPO_MEDIA_FALLIDA
                        if status in ('UNDELIVERED', 'FAILED')
                        else EstudianteEventoAprendizaje.TIPO_MEDIA_ENTREGADA
                        if status in ('DELIVERED', 'READ', 'RECEIVED')
                        else None
                    )
                    if tipo_ev:
                        registrar_evento(
                            tipo=tipo_ev,
                            estudiante=est,
                            metadata={
                                'twilio_sid': sid,
                                'status': status,
                                'error_code': error_code,
                                'whatsapp_log_id': log.pk,
                            },
                        )
            except Exception as te:
                logger.debug('telemetria status twilio: %s', te)
            return

        # Fallback para no perder trazabilidad de callbacks huérfanos.
        WhatsappLog.objects.create(
            telefono='desconocido',
            mensaje=f'[STATUS_CALLBACK:{status}]',
            mensaje_id=sid,
            tipo='SENT',
            estado=status,
            error_detalle=(
                f"{' '.join(x for x in (error_code, error_message) if x)} | "
                'Callback Twilio sin log SENT previo.'
            ).strip(' |'),
        )
    except Exception as e:
        logger.warning(f"⚠️ No se pudo registrar callback Twilio: {e}")

```

**Contrato**
- Entradas: POST de status callback Twilio.
- Salidas: None.
- Efectos: actualiza el `WhatsappLog` SENT con ese SID (estado, `error_detalle`). Si UNDELIVERED/FAILED y código de media, llama `reintentar_media_desde_log`. Puede crear un log huérfano si no había SENT previo. Registra telemetría de entrega.
- Excepciones: todo el cuerpo está en `except Exception` que solo loguea warning. No propaga.


### `_twilio_max_body_chars` — `core/views/twilio_transporte.py:180`

```python
# core/views/twilio_transporte.py:180
def _twilio_max_body_chars() -> int:
    """Retorna límite seguro para cuerpo de mensajes Twilio WhatsApp."""
    try:
        valor = int(getattr(settings, 'TWILIO_MAX_BODY_CHARS', 1500) or 1500)
    except (TypeError, ValueError):
        valor = 1500

    if valor < 200 or valor > 1590:
        return 1500
    return valor

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_segmentar_texto_twilio` — `core/views/twilio_transporte.py:191`

```python
# core/views/twilio_transporte.py:191
def _segmentar_texto_twilio(texto: str, max_chars: int = None) -> list:
    """Divide texto en segmentos compatibles con límite de Twilio."""
    texto = str(texto or '').strip()
    if not texto:
        return ['']

    limite = max_chars or _twilio_max_body_chars()

    try:
        from ..response_templates import dividir_contenido_seguro
        chunks = dividir_contenido_seguro(texto, max_chars=limite)
        if chunks:
            return chunks
    except Exception:
        pass

    # Fallback simple por longitud si la utilidad no está disponible.
    return [texto[i:i + limite] for i in range(0, len(texto), limite)]

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `youtube_hace_solo_enlace_en_texto` — `core/views/twilio_transporte.py:210`

```python
# core/views/twilio_transporte.py:210
def youtube_hace_solo_enlace_en_texto(url: str) -> bool:
    """True si la URL es página/embed (YouTube/Drive/…), no archivo directo adjuntarle por Twilio."""
    from ..twilio_media import url_no_es_media_directo

    return url_no_es_media_directo(url)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_enviar_mensaje_twilio_segmentado` — `core/views/twilio_transporte.py:216`

```python
# core/views/twilio_transporte.py:216
def _enviar_mensaje_twilio_segmentado(client, from_number: str, to_number: str, body: str, media_url: str = None) -> list:
    """Envía mensaje Twilio en segmentos seguros y devuelve [(sid, texto_enviado), ...]."""
    try:
        from core.sandbox_canal import _MetaSid, enviar_meta, sandbox_meta_activo

        if sandbox_meta_activo():
            result = enviar_meta(to_number, body or '', media_url=media_url)
            # Los llamadores leen mensaje.sid como en Twilio.
            sid = _MetaSid(result.get('mensaje_id') or '')
            return [(sid, body or '')] if result.get('success') else []
    except Exception:
        logger.exception('sandbox_meta_intercept_segmentado')

    from ..twilio_media import (
        cuerpo_con_enlace_archivo,
        es_error_media_twilio,
        es_url_s3_o_firmada,
        normalizar_media_url_s3,
        preparar_url_media_whatsapp,
        url_no_es_media_directo,
    )

    body_limpio = str(body or '').strip()
    media_limpia = normalizar_media_url_s3(media_url)
    # Páginas (YouTube/Drive): no adjuntar; solo enlace externo (nunca S3).
    if media_limpia and url_no_es_media_directo(media_limpia):
        if not es_url_s3_o_firmada(media_limpia):
            body_limpio = cuerpo_con_enlace_archivo(body_limpio or TWILIO_CAPTION_ADJUNTO, media_limpia)
        else:
            logger.warning('📎 URL página apunta a S3; no se envía en texto | %s', media_limpia[:120])
        media_limpia = None
    elif media_limpia:
        try:
            preparada = preparar_url_media_whatsapp(media_limpia)
            # None = video ilegible: no adjuntar y no enviar link S3.
            if preparada is None:
                logger.warning(
                    '📎 Video no adjuntable; se omite media (sin enlace S3) | %s',
                    media_limpia[:120],
                )
                media_limpia = None
            else:
                media_limpia = preparada or media_limpia
        except Exception as prep_err:
            logger.warning('📎 preparar_url_media_whatsapp falló (se envía original): %s', prep_err)
    # Adjunto sin texto: va solo, sin relleno genérico.
    # Sin media y sin texto útil: no spamear al estudiante.
    if not body_limpio and not media_limpia:
        return []

    enviados = []
    from_limpio = str(from_number or '').strip()
    to_limpio = str(to_number or '').strip()
    status_cb = str(getattr(settings, 'TWILIO_STATUS_CALLBACK_URL', '') or '').strip()

    segmentos = _segmentar_texto_twilio(body_limpio)

    for idx, segmento in enumerate(segmentos):
        seg_txt = (segmento or '').strip()
        params = {
            'from_': from_limpio,
            'to': to_limpio,
        }
        # Solo llega vacío cuando el adjunto va sin texto: Twilio lo manda solo.
        if seg_txt:
            params['body'] = seg_txt
        if status_cb:
            params['status_callback'] = status_cb

        # Adjuntar media solo en el primer segmento (Twilio descarga la URL; el alumno no ve el link).
        if media_limpia and idx == 0:
            params['media_url'] = [media_limpia]

        try:
            mensaje = client.messages.create(**params)
        except Exception as media_err:
            if es_error_media_twilio(media_err) and media_limpia and idx == 0:
                # Sin fallback a link S3: solo caption/texto.
                params.pop('media_url', None)
                if not (params.get('body') or '').strip():
                    params['body'] = TWILIO_CAPTION_ADJUNTO
                logger.warning(
                    '📎 Media Twilio falló en create (%s); reintento solo texto (sin URL S3) | url=%s',
                    media_err,
                    media_limpia[:120],
                )
                mensaje = client.messages.create(**params)
            else:
                raise

        enviados.append((mensaje, params.get('body', '') or seg_txt))

    return enviados
```

**Contrato**
- Entradas: cliente Twilio ya construido, from, to, body, media_url opcional.
- Salidas: lista de `(mensaje, texto)` o `[]` si no hay nada que enviar. En sandbox Meta devuelve `[(_MetaSid, body)]` o `[]`.
- Efectos: `messages.create` por segmento. Status callback si `TWILIO_STATUS_CALLBACK_URL`. Reintento solo-texto ante error de media. No escribe `WhatsappLog` (lo hace el caller).
- Excepciones: el intercept sandbox traga errores y sigue a Twilio. Errores de `messages.create` que no son de media se propagan.

