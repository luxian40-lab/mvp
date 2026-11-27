"""Carrusel de cursos de AgriCapital en la línea 3.

Solo AgriCapital (EKI_AGRICAPITAL_CLIENTE_ID). Tras el Flow muestra el
carrusel de cursos_whatsapp; Ver curso inscribe ese y abre la clase.
Otros clientes de la línea 3 no pasan por aquí.
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


def _solo_agricapital(cliente_id: int | None) -> bool:
    from core.lineas.registro_agricapital import es_cliente_agricapital

    return es_cliente_agricapital(cliente_id)


def cursos_del_cliente(cliente_id: int):
    """Los del carrusel WhatsApp. Si no marcó, los activos de la empresa."""
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


def ofrecer_tras_registro(telefono: str, cliente_id: int | None = None) -> None:
    """Después del formulario, solo AgriCapital ve el carrusel."""
    from core.lineas.registro_abrir import _cliente_guardado, _ficha, es_turno_registro

    if not es_turno_registro():
        return
    if cliente_id is None:
        ficha = _ficha(telefono)
        if ficha is None:
            return
        cliente_id = ficha.cliente_id or _cliente_guardado(telefono)
    if not _solo_agricapital(cliente_id):
        return
    atender_cursos(telefono, '', cliente_id)


def atender_cursos(telefono: str, body: str, cliente_id: int | None) -> None:
    """Carrusel AgriCapital. Una tarjeta elegida inscribe ese curso."""
    from core.lineas.registro_abrir import _avisar

    if not _solo_agricapital(cliente_id):
        return
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
    from core.agentes.nati import normalizar_telefono_whatsapp

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
    from core.lineas.registro_abrir import _avisar, envio_desde_linea_registro

    try:
        with envio_desde_linea_registro(forzar=True):
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
    from core.lineas.registro_abrir import _avisar, envio_desde_linea_registro

    try:
        with envio_desde_linea_registro(forzar=True):
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
    from core.lineas.registro_abrir import _avisar, envio_desde_linea_registro

    filas = [(f'ver_curso_{curso.id}', (curso.nombre or 'Curso')[:24], '') for curso in cursos]
    try:
        with envio_desde_linea_registro(forzar=True):
            resultado = enviar_meta_lista(
                telefono, CUERPO_OFERTA, 'Ver cursos', filas, agente_evento='registro_cursos',
            )
    except OSError:
        logger.exception('registro_lista_cursos')
        resultado = {'success': False}
    if not resultado.get('success'):
        nombres = ', '.join(curso.nombre for curso in cursos if curso.nombre)
        _avisar(telefono, f'{CUERPO_OFERTA} {nombres}')


def _respeta_ventana() -> bool:
    """Env gana. Si está apagado, manda el checkbox de Configuración Global.

    EKI_REGISTRO_VENTANA_BD=false evita la base (tests sin BD).
    """
    from django.conf import settings

    if getattr(settings, 'EKI_REGISTRO_RESPETA_VENTANA', False):
        return True
    if not getattr(settings, 'EKI_REGISTRO_VENTANA_BD', True):
        return False
    try:
        from core.models import ConfiguracionGlobal

        return bool(ConfiguracionGlobal.get_solo().registro_respeta_ventana)
    except Exception:
        logger.exception('registro_ventana_flag')
        return True


def _ventana_ok(ficha) -> bool:
    """Con el flag apagado no consulta: se comporta como antes."""
    if not _respeta_ventana():
        return True
    from core.campanas.reenganche_meta import ventana_abierta
    from core.canal.sandbox_canal import phone_id_de_salida

    return ventana_abierta(ficha, phone_id=phone_id_de_salida())


def _omitir_envio_libre(ficha) -> bool:
    """True si el flag de ventana está on y no hay ventana en la línea de salida."""
    return bool(ficha is not None and _respeta_ventana() and not _ventana_ok(ficha))


def _plantilla_retoma() -> tuple[str, str]:
    """(nombre Meta, url imagen). Vacío = no hay plantilla configurada."""
    from django.conf import settings

    nombre = (getattr(settings, 'EKI_REGISTRO_REENGANCHE_PLANTILLA', '') or '').strip()
    imagen = (getattr(settings, 'EKI_REGISTRO_REENGANCHE_IMAGEN', '') or '').strip()
    return nombre, imagen


def _retoma_recien_enviada(telefono: str) -> bool:
    """Una plantilla de retoma cada 20 h. Evita ráfaga si vuelven a tocar Continuar."""
    from datetime import timedelta

    from django.utils import timezone

    from core.models import WhatsappLog
    from core.agentes.nati import normalizar_telefono_whatsapp

    tel = normalizar_telefono_whatsapp(telefono) or (telefono or '')
    if not tel:
        return True
    return WhatsappLog.objects.filter(
        telefono__in=[tel, f'+{tel}'],
        agente_usado='registro_reenganche',
        fecha__gte=timezone.now() - timedelta(hours=20),
    ).exists()


def _enviar_retoma_si_toca(telefono: str, ficha) -> None:
    """Ventana cerrada: plantilla UTILITY, nunca media de sesión. No avanza el paso."""
    nombre, imagen = _plantilla_retoma()
    if not nombre or not imagen or _retoma_recien_enviada(telefono):
        return
    from core.lineas.registro_abrir import phone_id_linea_registro
    from core.lineas.sender import sender_de_linea

    progreso = _progreso_activo(ficha)
    curso = getattr(progreso, 'curso', None)
    modulo = getattr(progreso, 'modulo_actual', None)
    variables = {
        '1': (getattr(ficha, 'nombre', None) or 'Estudiante')[:80],
        '2': (getattr(curso, 'nombre', None) or 'su curso')[:80],
        '3': f'Modulo {getattr(modulo, "numero", None) or ""}'.strip() or 'su módulo',
    }
    phone_id = phone_id_linea_registro()
    if not phone_id:
        logger.info('registro_retoma_sin_linea')
        return
    try:
        sender_de_linea(phone_id).plantilla_imagen(
            telefono, nombre, imagen, variables, agente='registro_reenganche',
        )
    except OSError:
        logger.exception('registro_retoma')


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
    # Ventana cerrada: inscripción queda; sin dump de sesión (evita 131047 en ráfaga).
    if not _ventana_ok(ficha):
        logger.info('registro_ventana_cerrada_omitido curso=%s', curso.id)
        return
    _avisar(telefono, TEXTO_INSCRITO.format(nombre=curso.nombre))
    _entregar_primera_clase(telefono, ficha, progreso)


def _recordar_curso(ficha, curso_id: int) -> None:
    """El listo siguiente avanza este curso; con el flag, deja el saludo pendiente."""
    from core.curso.inicio_curso import inicio_ya_entregado, marcar_inicio_pendiente

    ctx = dict(getattr(ficha, 'contexto_temporal', None) or {})
    mismo = ctx.get('curso_activo_id') == curso_id
    dejar_pendiente = (
        _respeta_ventana() and not inicio_ya_entregado(ficha, curso_id)
        and ctx.get('inicio_pendiente_curso_id') != curso_id
    )
    if mismo and not dejar_pendiente:
        return
    ctx['curso_activo_id'] = curso_id
    if dejar_pendiente:
        marcar_inicio_pendiente(ctx, curso_id)
    ficha.contexto_temporal = ctx
    ficha.save(update_fields=['contexto_temporal'])


def _abrir_si_no_empezo(ficha, progreso, *, marcar: bool = True) -> str:
    """Saludo y módulo 1 solo si ese curso todavía no se mostró."""
    from core.curso.inicio_curso import curso_sin_empezar, mensaje_primera_entrega

    modulo = getattr(progreso, 'modulo_actual', None)
    if modulo is None or not curso_sin_empezar(ficha, progreso, modulo):
        return ''
    return mensaje_primera_entrega(ficha, progreso, modulo, marcar=marcar) or ''


def _entregar_primera_clase(telefono: str, ficha, progreso) -> bool:
    """Arma y manda el saludo. Con flag on solo marca entregado si Graph aceptó."""
    from core.curso.inicio_curso import marcar_inicio_entregado
    from core.lineas.registro_abrir import _avisar

    deferir = _respeta_ventana()
    try:
        clase = _abrir_si_no_empezo(ficha, progreso, marcar=not deferir)
    except DatabaseError:
        logger.exception('registro_primera_clase')
        return False
    if not clase:
        return False
    resultado = _avisar(telefono, clase, agente='registro_cursos')
    if deferir and resultado.get('success'):
        try:
            from core.curso.inicio_curso import _partes_del_modulo

            modulo = getattr(progreso, 'modulo_actual', None)
            if getattr(modulo, 'pk', None):
                _partes_del_modulo(progreso, modulo, persistir=True)
            marcar_inicio_entregado(ficha, progreso.curso_id)
        except DatabaseError:
            logger.exception('registro_marca_inicio')
    return bool(resultado.get('success'))


def _progreso_activo(ficha):
    from core.models import ProgresoEstudiante

    curso_id = (getattr(ficha, 'contexto_temporal', None) or {}).get('curso_activo_id')
    if not curso_id:
        return None
    return (
        ProgresoEstudiante.objects.filter(
            estudiante_id=ficha.id, curso_id=curso_id, completado=False,
        )
        .select_related('curso', 'modulo_actual')
        .first()
    )


def _reintentar_primera_si_falta(telefono: str, ficha) -> bool:
    """Tras skip por ventana: al Continuar, entrega el saludo si ya puede."""
    from core.curso.inicio_curso import curso_sin_empezar, falta_primera_entrega

    if not _respeta_ventana() or not _ventana_ok(ficha):
        return False
    progreso = _progreso_activo(ficha)
    if progreso is None:
        return False
    modulo = getattr(progreso, 'modulo_actual', None)
    if not (
        falta_primera_entrega(ficha, progreso, modulo)
        or curso_sin_empezar(ficha, progreso, modulo)
    ):
        return False
    return _entregar_primera_clase(telefono, ficha, progreso)


def _foto_progreso(progreso) -> dict | None:
    """Campos que continuar_leccion mueve antes de que Meta confirme el envío."""
    if progreso is None or not getattr(progreso, 'pk', None):
        return None
    return {
        'paso_actual_modulo': progreso.paso_actual_modulo,
        'modulo_actual_id': progreso.modulo_actual_id,
        'esperando_respuesta_evaluacion_paso': progreso.esperando_respuesta_evaluacion_paso,
        'paso_evaluacion_paso_id': getattr(progreso, 'paso_evaluacion_paso_id', None),
        'completado': progreso.completado,
    }


def _restaurar_progreso(progreso_id: int, foto: dict) -> None:
    from core.models import ProgresoEstudiante

    ProgresoEstudiante.objects.filter(pk=progreso_id).update(**foto)


def _avanzar(telefono: str, body: str) -> bool:
    """listo y continuar siguen el curso en esta línea. No reabre el carrusel."""
    import importlib

    responder = importlib.import_module(
        'core.conversacion.intents.continuar_leccion',
    ).responder
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
    # Cerrada: no llamar continuar_leccion (eso sube el paso aunque Meta no entregue).
    if _omitir_envio_libre(ficha):
        logger.info('registro_ventana_cerrada_omitido motivo=listo_avance')
        try:
            _enviar_retoma_si_toca(telefono, ficha)
        except DatabaseError:
            logger.exception('registro_retoma')
        return True
    try:
        if _reintentar_primera_si_falta(telefono, ficha):
            return True
    except DatabaseError:
        logger.exception('registro_reintento_primera')
    progreso = _progreso_activo(ficha)
    foto = _foto_progreso(progreso)
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
        resultado = _avisar(telefono, texto, agente='registro_cursos') or {}
        if foto and not resultado.get('success'):
            logger.info('registro_envio_fallo_restaura progreso=%s', progreso.pk)
            try:
                _restaurar_progreso(progreso.pk, foto)
            except DatabaseError:
                logger.exception('registro_restaura_progreso')
    return True
