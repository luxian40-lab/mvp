"""Cursos del enlace en la línea 3.

El carrusel es el de la organización que vino en el enlace, no el de la
línea principal. Con una sola tarjeta WhatsApp no arma carrusel: sale un
botón. Sin foto https, sale una lista.
"""
from __future__ import annotations

import logging

from django.db import DatabaseError

logger = logging.getLogger(__name__)

CUERPO_OFERTA = 'Elija un curso. La clase sigue en este chat.'
TEXTO_SIN_ENLACE = 'Para ver los cursos, abra el enlace que le enviaron.'
TEXTO_SIN_CURSOS = 'Su registro quedó. Esta organización todavía no tiene cursos en el enlace.'
TEXTO_INSCRITO = 'Quedó en {nombre}.'
TEXTO_OTRO_CURSO = 'Ese curso no está en el enlace de su organización.'


def cursos_del_cliente(cliente_id: int):
    """Los que la organización marcó para WhatsApp. Si no marcó, los suyos activos."""
    from core.models import Cliente, Curso

    cliente = Cliente.objects.filter(pk=cliente_id, activo=True).first()
    if cliente is None:
        return []
    marcados = cliente.cursos_whatsapp.filter(activo=True)
    if marcados.exists():
        return list(marcados.order_by('orden', 'nombre', 'id'))
    return list(
        Curso.objects.filter(cliente_id=cliente_id, activo=True).order_by('orden', 'nombre', 'id')
    )


def modo_de_oferta(cantidad: int, con_foto: bool) -> str:
    """vacio, boton, carrusel o lista."""
    if cantidad <= 0:
        return 'vacio'
    if cantidad == 1:
        return 'boton'
    if con_foto and 2 <= cantidad <= 10:
        return 'carrusel'
    return 'lista'


def ofrecer_tras_registro(telefono: str) -> None:
    """Después del formulario, en esta línea, muestra los cursos del enlace."""
    from core.lineas.registro_abrir import _cliente_guardado, _ficha, es_turno_registro

    if not es_turno_registro():
        return
    ficha = _ficha(telefono)
    if ficha is None:
        return
    cliente_id = ficha.cliente_id or _cliente_guardado(telefono)
    atender_cursos(telefono, '', cliente_id)


def atender_cursos(telefono: str, body: str, cliente_id: int | None) -> None:
    """Carrusel, botón o lista. Una tarjeta elegida inscribe, si es de este enlace."""
    from core.lineas.registro_abrir import _avisar

    if _es_info(body):
        _contar(telefono, _id_de_prefijo(body, 'info_curso_'), cliente_id)
        return
    curso_id = _id_de_prefijo(body, 'ver_curso_')
    if curso_id is not None:
        _inscribir(telefono, curso_id, cliente_id)
        return
    if _avanzar(telefono, body):
        return
    if not cliente_id:
        _avisar(telefono, TEXTO_SIN_ENLACE)
        return
    if _oferta_recien_enviada(telefono):
        return
    try:
        cursos = cursos_del_cliente(cliente_id)
    except DatabaseError:
        logger.exception('registro_cursos_listar')
        _avisar(telefono, TEXTO_SIN_CURSOS)
        return
    if not cursos:
        _avisar(telefono, TEXTO_SIN_CURSOS)
        return
    tarjetas = [_tarjeta(curso) for curso in cursos]
    con_foto = all(str(tarjeta.get('imagen') or '').startswith('https://') for tarjeta in tarjetas)
    modo = modo_de_oferta(len(cursos), con_foto)
    if modo == 'carrusel':
        _enviar_carrusel(telefono, tarjetas[:10])
        return
    if modo == 'boton':
        _enviar_boton(telefono, cursos[0])
        return
    _enviar_lista(telefono, cursos[:10])


def _oferta_recien_enviada(telefono: str) -> bool:
    """El carrusel acaba de salir. Otro mensaje enseguida no lo repite."""
    from datetime import timedelta

    from django.utils import timezone

    from core.models import WhatsappLog
    from core.nati import normalizar_telefono_whatsapp

    tel = normalizar_telefono_whatsapp(telefono) or (telefono or '')
    if not tel:
        return False
    return WhatsappLog.objects.filter(
        telefono__in=[tel, f'+{tel}'],
        tipo='SENT',
        estado='SENT',
        agente_usado='registro_cursos',
        mensaje__startswith=CUERPO_OFERTA,
        fecha__gte=timezone.now() - timedelta(minutes=2),
    ).exists()


def _es_info(body: str) -> bool:
    return _id_de_prefijo(body, 'info_curso_') is not None


def _id_de_prefijo(body: str, prefijo: str) -> int | None:
    texto = (body or '').strip()
    if texto.startswith(prefijo) and texto[len(prefijo):].isdigit():
        return int(texto[len(prefijo):])
    return None


def _contar(telefono: str, curso_id: int | None, cliente_id: int | None) -> None:
    from core.lineas.registro_abrir import _avisar

    if not cliente_id or curso_id is None:
        _avisar(telefono, TEXTO_SIN_ENLACE)
        return
    try:
        cursos = {curso.id: curso for curso in cursos_del_cliente(cliente_id)}
    except DatabaseError:
        logger.exception('registro_info_curso')
        _avisar(telefono, TEXTO_SIN_CURSOS)
        return
    curso = cursos.get(curso_id)
    if curso is None:
        _avisar(telefono, TEXTO_OTRO_CURSO)
        return
    resumen = ' '.join((curso.descripcion or '').split()) or curso.nombre
    _avisar(telefono, f'{curso.nombre}. {resumen}'[:500])


def _tarjeta(curso) -> dict:
    from core.curso.cursos_generales import _imagen_de_curso, _url_de_curso, texto_tarjeta

    resumen = ' '.join((curso.descripcion or '').split())[:120]
    url = _url_de_curso(curso)
    return {
        'body': texto_tarjeta({'nombre': curso.nombre, 'resumen': resumen, 'url': url}),
        'imagen': _imagen_de_curso(curso),
        'url': url,
        'titulo': curso.nombre,
        'botones': [
            (f'ver_curso_{curso.id}', 'Ver curso'),
            (f'info_curso_{curso.id}', 'Más información'),
        ],
    }


def _enviar_carrusel(telefono: str, tarjetas: list[dict]) -> None:
    from core.lineas.envio import enviar_meta_carrusel
    from core.lineas.registro_abrir import _avisar

    try:
        resultado = enviar_meta_carrusel(
            telefono, CUERPO_OFERTA, tarjetas, agente_evento='registro_cursos',
        )
    except OSError:
        logger.exception('registro_carrusel')
        resultado = {'success': False}
    if not resultado.get('success'):
        _avisar(telefono, CUERPO_OFERTA)


def _enviar_boton(telefono: str, curso) -> None:
    from core.lineas.envio import enviar_meta_botones
    from core.lineas.registro_abrir import _avisar

    try:
        resultado = enviar_meta_botones(
            telefono,
            f'{CUERPO_OFERTA}\n{curso.nombre}',
            [(f'ver_curso_{curso.id}', 'Ver curso')],
            agente_evento='registro_cursos',
        )
    except OSError:
        logger.exception('registro_boton_curso')
        resultado = {'success': False}
    if not resultado.get('success'):
        _avisar(telefono, f'{CUERPO_OFERTA} {curso.nombre}')


def _enviar_lista(telefono: str, cursos) -> None:
    from core.lineas.envio import enviar_meta_lista
    from core.lineas.registro_abrir import _avisar

    filas = [(f'ver_curso_{curso.id}', (curso.nombre or 'Curso')[:24], '') for curso in cursos]
    try:
        resultado = enviar_meta_lista(
            telefono, CUERPO_OFERTA, 'Ver cursos', filas, agente_evento='registro_cursos',
        )
    except OSError:
        logger.exception('registro_lista_cursos')
        resultado = {'success': False}
    if not resultado.get('success'):
        nombres = ', '.join(curso.nombre for curso in cursos if curso.nombre)
        _avisar(telefono, f'{CUERPO_OFERTA} {nombres}')


def _inscribir(telefono: str, curso_id: int, cliente_id: int | None) -> None:
    from core.curso.inscripcion_curso import inscribir_estudiante_en_curso
    from core.lineas.registro_abrir import _avisar, _ficha

    if not cliente_id:
        _avisar(telefono, TEXTO_SIN_ENLACE)
        return
    try:
        cursos = {curso.id: curso for curso in cursos_del_cliente(cliente_id)}
        curso = cursos.get(curso_id)
        ficha = _ficha(telefono)
        if curso is None or ficha is None:
            _avisar(telefono, TEXTO_OTRO_CURSO)
            return
        progreso, _creado = inscribir_estudiante_en_curso(ficha, curso)
    except DatabaseError:
        logger.exception('registro_inscribir')
        _avisar(telefono, TEXTO_OTRO_CURSO)
        return
    try:
        _recordar_curso(ficha, curso.id)
    except DatabaseError:
        logger.exception('registro_curso_activo')
    _avisar(telefono, TEXTO_INSCRITO.format(nombre=curso.nombre))
    try:
        clase = _abrir_si_no_empezo(ficha, progreso)
    except DatabaseError:
        logger.exception('registro_primera_clase')
        return
    if clase:
        _avisar(telefono, clase)


def _recordar_curso(ficha, curso_id: int) -> None:
    """El listo siguiente avanza este curso, el que la persona acaba de elegir."""
    ctx = dict(getattr(ficha, 'contexto_temporal', None) or {})
    if ctx.get('curso_activo_id') == curso_id:
        return
    ctx['curso_activo_id'] = curso_id
    ficha.contexto_temporal = ctx
    ficha.save(update_fields=['contexto_temporal'])


def _abrir_si_no_empezo(ficha, progreso) -> str:
    """Saludo y módulo 1 solo si ese curso todavía no se mostró."""
    from core.curso.inicio_curso import curso_sin_empezar, mensaje_primera_entrega

    modulo = getattr(progreso, 'modulo_actual', None)
    if modulo is None or not curso_sin_empezar(ficha, progreso, modulo):
        return ''
    return mensaje_primera_entrega(ficha, progreso, modulo) or ''


def _avanzar(telefono: str, body: str) -> bool:
    """listo y continuar siguen el curso en esta línea. No reabre el carrusel."""
    from core.conversacion.intents.continuar_leccion import responder
    from core.conversacion.response_templates import (
        LECCION_EN_CURSO,
        _es_mensaje_listo_avance_curso,
        soltar_turno_entrega_actual,
    )
    from core.lineas.registro_abrir import _avisar, _ficha

    if not _es_mensaje_listo_avance_curso(body):
        return False
    ficha = _ficha(telefono)
    if ficha is None:
        return False
    texto = ''
    try:
        texto = responder(
            'continuar_leccion',
            getattr(ficha, 'nombre', None) or 'Estudiante',
            {'estudiante_id': ficha.id, 'mensaje_original': body},
        ) or ''
    except DatabaseError:
        logger.exception('registro_listo')
        texto = ''
    finally:
        try:
            soltar_turno_entrega_actual()
        except DatabaseError:
            logger.exception('registro_soltar_turno')
    if texto and texto != LECCION_EN_CURSO:
        _avisar(telefono, texto)
    return True
