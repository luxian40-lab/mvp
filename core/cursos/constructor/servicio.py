"""Servicios del constructor (slice 5.1: texto). Flag off: mutaciones no escriben."""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Max


def constructor_activo() -> bool:
    return bool(getattr(settings, 'EKI_CONSTRUCTOR_CURSOS', False))


def estructura_desde_snap(snap: dict) -> dict:
    """Vocabulario del constructor (bloques/mensajes) a partir del ensamblado real."""
    modulos_out = []
    for mod in snap.get('modulos') or []:
        bloques_out = []
        for sec in mod.get('secciones') or []:
            bloques_out.append({
                'id': sec['id'],
                'orden': sec['orden'],
                'titulo': sec.get('titulo') or '',
                'activa': bool(sec.get('activa')),
                'mensajes': list(sec.get('pasos') or []),
            })
        modulos_out.append({
            'id': mod['id'],
            'numero': mod['numero'],
            'titulo': mod['titulo'],
            'descripcion': mod.get('descripcion') or '',
            'publicado_wa': bool(mod.get('publicado_wa')),
            'bloques': bloques_out,
        })
    return {
        'schema': 1,
        'curso_id': snap.get('curso_id'),
        'curso_nombre': snap.get('curso_nombre') or '',
        'modulos': modulos_out,
    }


def estructura_curso(curso) -> dict:
    """Árbol curso → módulos → bloques → mensajes. Un solo walk (el ensamblador)."""
    return estructura_desde_snap(preview_ensamblado(curso))


def crear_modulo(curso, *, titulo: str, descripcion: str = ''):
    """Siembra del constructor: modo pasos, publicado_wa=False, un bloque vacío.

    No comparte camino con «Añadir clase rápida» (modo legacy si el curso es
    de clases, duración 7, título «Clase N»). Unificarlos es otro corte.
    Flag off → None.
    """
    if not constructor_activo():
        return None

    from core.models import Modulo, SeccionModulo

    titulo_limpio = (titulo or '').strip()
    if not titulo_limpio:
        raise ValueError('titulo es obligatorio')

    with transaction.atomic():
        locked = type(curso).objects.select_for_update().get(pk=curso.pk)
        ultimo = (
            Modulo.objects.filter(curso=locked)
            .aggregate(m=Max('numero'))
            .get('m')
        )
        numero = (ultimo or 0) + 1
        modulo = Modulo.objects.create(
            curso=locked,
            numero=numero,
            titulo=titulo_limpio[:200],
            descripcion=(descripcion or '').strip(),
            contenido='',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
            # Guardar en constructor no publica (modelo default histórico = True).
            publicado_wa=False,
        )
        SeccionModulo.objects.create(
            modulo=modulo,
            orden=1,
            titulo='Bloque 1',
            activa=True,
        )
    return modulo


def crear_bloque(modulo, *, titulo: str = ''):
    """Añade un bloque (SeccionModulo) al módulo. Flag off → None."""
    if not constructor_activo():
        return None

    from core.models import SeccionModulo

    with transaction.atomic():
        locked = type(modulo).objects.select_for_update().get(pk=modulo.pk)
        ultimo = (
            SeccionModulo.objects.filter(modulo=locked)
            .aggregate(m=Max('orden'))
            .get('m')
        )
        orden = (ultimo or 0) + 1
        titulo_final = (titulo or '').strip() or f'Bloque {orden}'
        return SeccionModulo.objects.create(
            modulo=locked,
            orden=orden,
            titulo=titulo_final[:200],
            activa=True,
        )


def crear_mensaje_texto(bloque, *, contenido: str, titulo: str = '', activo: bool = False):
    """Mensaje de texto (PasoModulo contenido) en el bloque. Flag off → None."""
    if not constructor_activo():
        return None

    from core.models import PasoModulo

    texto = (contenido or '').strip()
    if not texto:
        raise ValueError('contenido es obligatorio')

    with transaction.atomic():
        locked = type(bloque).objects.select_for_update().get(pk=bloque.pk)
        modulo = type(locked.modulo).objects.select_for_update().get(pk=locked.modulo_id)
        ultimo = (
            PasoModulo.objects.filter(modulo=modulo)
            .aggregate(m=Max('orden'))
            .get('m')
        )
        orden = (ultimo or 0) + 1
        return PasoModulo.objects.create(
            modulo=modulo,
            seccion=locked,
            orden=orden,
            tipo=PasoModulo.TIPO_CONTENIDO,
            titulo=(titulo or '').strip()[:200],
            contenido=texto,
            media_url='',
            activo=bool(activo),
            requiere_listo_para_avanzar=True,
        )


def actualizar_mensaje_texto(
    paso,
    *,
    contenido: str | None = None,
    titulo: str | None = None,
    activo: bool | None = None,
):
    """Edita solo campos de texto/activo. No publica. Flag off → None."""
    if not constructor_activo():
        return None

    from core.models import PasoModulo

    if paso.tipo != PasoModulo.TIPO_CONTENIDO:
        raise ValueError('solo mensajes de contenido de texto en slice 5.1')

    campos = []
    if contenido is not None:
        texto = (contenido or '').strip()
        if not texto:
            raise ValueError('contenido no puede quedar vacío')
        paso.contenido = texto
        campos.append('contenido')
    if titulo is not None:
        paso.titulo = (titulo or '').strip()[:200]
        campos.append('titulo')
    if activo is not None:
        paso.activo = bool(activo)
        campos.append('activo')
    if not campos:
        return paso
    paso.save(update_fields=campos)
    return paso


def preview_ensamblado(curso) -> dict:
    """Misma congelación que publicar (ensamblador real). Lectura; no depende del flag."""
    from core.cursos.autoria.ensamblado import congelar_ensamblado

    return congelar_ensamblado(curso)


def mover_bloque(bloque, direction: str) -> bool:
    """↑↓ de bloque dentro del módulo. Flag off → False."""
    if not constructor_activo():
        return False
    from core.curso.orden_bloques import intercambiar_orden

    return bool(intercambiar_orden(bloque, direction))


def mover_mensaje(paso, direction: str) -> bool:
    """↑↓ de mensaje dentro de su bloque (no cruza a otro bloque). Flag off → False.

    El ``orden`` sigue siendo único en el módulo; solo se intercambia con el
    vecino de la misma sección.
    """
    if not constructor_activo():
        return False
    if direction not in ('up', 'down') or not paso or not paso.pk:
        return False

    from core.models import PasoModulo

    with transaction.atomic():
        locked = PasoModulo.objects.select_for_update().get(pk=paso.pk)
        hermanos = list(
            PasoModulo.objects.select_for_update()
            .filter(seccion_id=locked.seccion_id)
            .order_by('orden', 'id')
        )
        try:
            idx = next(i for i, p in enumerate(hermanos) if p.pk == locked.pk)
        except StopIteration:
            return False
        target = idx - 1 if direction == 'up' else idx + 1
        if target < 0 or target >= len(hermanos):
            return False
        otro = hermanos[target]
        a, b = locked.orden, otro.orden
        if a == b:
            return False
        temp = (
            PasoModulo.objects.filter(modulo_id=locked.modulo_id)
            .aggregate(m=Max('orden'))
            .get('m')
            or 0
        ) + 1000
        PasoModulo.objects.filter(pk=locked.pk).update(orden=temp)
        PasoModulo.objects.filter(pk=otro.pk).update(orden=a)
        PasoModulo.objects.filter(pk=locked.pk).update(orden=b)
    return True


def adjuntar_media_mensaje(paso, *, media_url: str, activo: bool | None = None):
    """Adjunta URL de media a un mensaje de contenido (slice 5.4). Flag off → None.

    No sube archivos ni comprime: solo valida https y guarda la URL.
    Validaciones profundas Meta (tamaño/codec) siguen en el pipeline de media existente.
    """
    if not constructor_activo():
        return None

    from core.models import PasoModulo

    if paso.tipo != PasoModulo.TIPO_CONTENIDO:
        raise ValueError('solo mensajes de contenido admiten media en 5.4')
    url = (media_url or '').strip()
    if not url.startswith('https://'):
        raise ValueError('media_url debe ser https://')
    paso.media_url = url[:1000]
    campos = ['media_url']
    if activo is not None:
        paso.activo = bool(activo)
        campos.append('activo')
    paso.save(update_fields=campos)
    return paso


def crear_mensaje_evaluacion(
    bloque,
    *,
    pregunta: str,
    opcion_a: str,
    opcion_b: str,
    opcion_c: str = '',
    opcion_d: str = '',
    correcta: str,
    feedback_correcto: str = '',
    feedback_incorrecto: str = '',
    activo: bool = False,
):
    """Evaluación A–D (slice 5.5). Flag off → None. No publica."""
    if not constructor_activo():
        return None

    from core.models import PasoModulo

    enunciado = (pregunta or '').strip()
    if not enunciado:
        raise ValueError('pregunta es obligatoria')
    letra = (correcta or '').strip().upper()[:1]
    if letra not in ('A', 'B', 'C', 'D'):
        raise ValueError('correcta debe ser A, B, C o D')
    a = (opcion_a or '').strip()
    b = (opcion_b or '').strip()
    c = (opcion_c or '').strip()
    d = (opcion_d or '').strip()
    if not a or not b:
        raise ValueError('opcion_a y opcion_b son obligatorias')
    opciones = {'A': a, 'B': b, 'C': c, 'D': d}
    if not opciones[letra]:
        raise ValueError(f'la opción {letra} no puede estar vacía')

    with transaction.atomic():
        locked = type(bloque).objects.select_for_update().get(pk=bloque.pk)
        modulo = type(locked.modulo).objects.select_for_update().get(pk=locked.modulo_id)
        ultimo = (
            PasoModulo.objects.filter(modulo=modulo)
            .aggregate(m=Max('orden'))
            .get('m')
        )
        orden = (ultimo or 0) + 1
        return PasoModulo.objects.create(
            modulo=modulo,
            seccion=locked,
            orden=orden,
            tipo=PasoModulo.TIPO_EVAL_OPC,
            titulo='',
            contenido=enunciado,
            media_url='',
            eval_opcion_a=a,
            eval_opcion_b=b,
            eval_opcion_c=c,
            eval_opcion_d=d,
            respuesta_correcta=letra,
            feedback_correcto=(feedback_correcto or '').strip(),
            feedback_incorrecto=(feedback_incorrecto or '').strip(),
            activo=bool(activo),
            requiere_listo_para_avanzar=True,
        )


def publicar_desde_constructor(curso, *, nota: str = ''):
    """Publica versión inmutable vía autoría (bloque 4). No mueve cohorte.

    Requiere constructor activo. Si EKI_CURSO_VERSIONES está apagado, ``publicar``
    no escribe y devuelve None (mismo contrato que el admin de versiones).
    """
    if not constructor_activo():
        return None
    from core.cursos.autoria.servicio import publicar

    return publicar(curso, nota=nota)


def mover_modulo(modulo, direction: str) -> bool:
    """↑↓ de módulo por ``numero`` dentro del curso. Flag off → False."""
    if not constructor_activo():
        return False
    if direction not in ('up', 'down') or not modulo or not modulo.pk:
        return False

    from core.models import Modulo

    with transaction.atomic():
        locked = Modulo.objects.select_for_update().get(pk=modulo.pk)
        hermanos = list(
            Modulo.objects.filter(curso_id=locked.curso_id).order_by('numero', 'id')
        )
        try:
            idx = next(i for i, m in enumerate(hermanos) if m.pk == locked.pk)
        except StopIteration:
            return False
        target = idx - 1 if direction == 'up' else idx + 1
        if target < 0 or target >= len(hermanos):
            return False
        otro = hermanos[target]
        a, b = locked.numero, otro.numero
        if a == b:
            return False
        temp = (Modulo.objects.filter(curso_id=locked.curso_id).aggregate(m=Max('numero')).get('m') or 0) + 1000
        Modulo.objects.filter(pk=locked.pk).update(numero=temp)
        Modulo.objects.filter(pk=otro.pk).update(numero=a)
        Modulo.objects.filter(pk=locked.pk).update(numero=b)
    return True


def editar_mensaje(paso, *, contenido: str, titulo: str = '', activo: bool = False):
    """Edita el texto de un mensaje ya creado. No publica. Flag off → None."""
    if not constructor_activo():
        return None
    from core.models import PasoModulo

    if paso.tipo == PasoModulo.TIPO_CONTENIDO:
        return actualizar_mensaje_texto(
            paso, contenido=contenido, titulo=titulo, activo=activo,
        )
    if paso.tipo != PasoModulo.TIPO_EVAL_OPC:
        raise ValueError('ese tipo de mensaje no se edita en el constructor')
    texto = (contenido or '').strip()
    if not texto:
        raise ValueError('contenido no puede quedar vacío')
    paso.contenido = texto
    paso.titulo = (titulo or '').strip()[:200]
    paso.activo = bool(activo)
    paso.save(update_fields=['contenido', 'titulo', 'activo'])
    return paso


def subir_archivo_mensaje(paso, uploaded_file):
    """Sube el archivo por el mismo pipeline del admin (tope y video Meta). Flag off → None."""
    if not constructor_activo():
        return None
    from django.core.exceptions import ValidationError

    from core.admin._common import guardar_upload_admin_media_resultado
    from core.models import PasoModulo

    if paso.tipo != PasoModulo.TIPO_CONTENIDO:
        raise ValueError('solo un mensaje de contenido admite archivo')
    if uploaded_file is None:
        raise ValueError('falta el archivo')
    try:
        resultado = guardar_upload_admin_media_resultado(
            uploaded_file,
            carpeta='modulos/pasos',
            prefix=f'modulo_{paso.modulo_id}',
        )
    except ValidationError as exc:
        msgs = getattr(exc, 'messages', None) or [str(exc)]
        raise ValueError(msgs[0] if msgs else 'el archivo no pasó la validación Meta') from exc
    url = (resultado.get('url') or '').strip()
    if not url:
        raise ValueError('el archivo se procesó pero no dejó URL')
    paso.media_url = url[:1000]
    campos = ['media_url']
    if resultado.get('media_wa_apto') is not None:
        paso.media_wa_apto = bool(resultado['media_wa_apto'])
        campos.append('media_wa_apto')
    paso.save(update_fields=campos)
    return paso


def actualizar_drip(curso, dias: int):
    """Días de espera entre módulos del curso. 0 = libre. Flag off → None."""
    if not constructor_activo():
        return None
    try:
        n = int(dias)
    except (TypeError, ValueError) as exc:
        raise ValueError('días de espera inválidos') from exc
    if n < 0 or n > 365:
        raise ValueError('días de espera entre 0 y 365')
    curso.dias_espera_entre_modulos = n
    curso.save(update_fields=['dias_espera_entre_modulos'])
    return curso


def actualizar_calendario_modulo(modulo, *, habilitado_desde, duracion_dias: int):
    """Calendario global del módulo y días estimados. Flag off → None."""
    if not constructor_activo():
        return None
    try:
        dias = int(duracion_dias)
    except (TypeError, ValueError) as exc:
        raise ValueError('duración inválida') from exc
    if dias < 1 or dias > 365:
        raise ValueError('duración entre 1 y 365 días')
    modulo.habilitado_desde = habilitado_desde
    modulo.duracion_dias = dias
    modulo.save(update_fields=['habilitado_desde', 'duracion_dias'])
    return modulo


def resumen_certificado(curso) -> dict:
    """Si el curso ya tiene plantilla de certificado. Solo lectura."""
    n = curso.plantillas_certificados.count()
    return {'plantillas': n, 'listo': n > 0}


def numeros_prueba_interna() -> set[str]:
    crudos = getattr(settings, 'EKI_CAMPANA_META_PRUEBA_NUMEROS', []) or []
    return {''.join(ch for ch in str(p) if ch.isdigit()) for p in crudos}


def probar_mensaje_interno(paso, telefono: str) -> dict:
    """Envía el texto del mensaje solo a un número de la lista interna. No inscribe."""
    if not constructor_activo():
        return {'success': False, 'error': 'constructor apagado'}
    tel = ''.join(ch for ch in (telefono or '') if ch.isdigit())
    if tel not in numeros_prueba_interna():
        raise ValueError('ese número no está autorizado para la prueba interna')
    cuerpo = (paso.contenido or '').strip()
    if not cuerpo:
        raise ValueError('el mensaje no tiene texto')
    phone_id = (getattr(settings, 'WHATSAPP_PHONE_ID', '') or '').strip()
    if not phone_id:
        raise ValueError('WHATSAPP_PHONE_ID vacío: no hay línea Meta para la prueba')
    from core.lineas.sender import sender_de_linea

    media = (paso.media_url or '').strip() or None
    return sender_de_linea(phone_id).texto(
        tel, cuerpo[:1024], media_url=media, agente='constructor_prueba',
    )
