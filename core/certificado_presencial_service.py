"""Emisión masiva de certificados (cursos presenciales, sin avance WhatsApp)."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from core.certificado_service import (
    enviar_certificado_whatsapp,
    generar_y_guardar_certificado,
    plantillas_selectables_para_curso,
    resolver_plantilla_certificado,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, Plantilla, ProgresoEstudiante
from core.models_certificados import Certificado, PlantillaCertificado


def plantillas_twilio_whatsapp() -> list[Plantilla]:
    """Plantillas Twilio aprobadas (HX…) para elegir en envío masivo."""
    return list(
        Plantilla.objects.filter(activa=True, aprobada_twilio=True)
        .exclude(twilio_template_sid__isnull=True)
        .exclude(twilio_template_sid='')
        .order_by('nombre_interno')
    )


def resolver_twilio_content_sid(
    *,
    plantilla_id: int | None = None,
    sid_manual: str | None = None,
) -> str:
    """Prioridad: plantilla admin → HX pegado a mano."""
    sid = (sid_manual or '').strip()
    if plantilla_id:
        pl = (
            Plantilla.objects.filter(pk=plantilla_id, activa=True)
            .exclude(twilio_template_sid__isnull=True)
            .exclude(twilio_template_sid='')
            .first()
        )
        if pl:
            return (pl.twilio_template_sid or '').strip()
    return sid


def marcar_cert_envio_pendiente(
    estudiante: Estudiante,
    certificado: Certificado,
    curso: Curso,
    *,
    cerrar_avance: bool = False,
) -> None:
    """Marca certificado para envío tras respuesta del estudiante (abre ventana WhatsApp)."""
    ctx = estudiante.contexto_temporal or {}
    ctx['cert_envio_pendiente'] = {
        'certificado_id': certificado.id,
        'curso_id': curso.id,
        'ts': timezone.now().isoformat(),
        'cerrar_avance': bool(cerrar_avance),
    }
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])


def limpiar_cert_envio_pendiente(estudiante: Estudiante) -> None:
    ctx = estudiante.contexto_temporal or {}
    if 'cert_envio_pendiente' not in ctx:
        return
    ctx.pop('cert_envio_pendiente', None)
    estudiante.contexto_temporal = ctx or None
    estudiante.save(update_fields=['contexto_temporal'])


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


def numeros_cierre_curso(curso: Curso) -> tuple[int | None, int | None]:
    """Penúltimo y último número de módulo del curso (cualquier curso)."""
    nums = list(
        Modulo.objects.filter(curso=curso).order_by('numero', 'id').values_list('numero', flat=True)
    )
    if not nums:
        return None, None
    ultimo = nums[-1]
    penultimo = nums[-2] if len(nums) >= 2 else None
    return penultimo, ultimo


def progreso_en_tramo_cierre(progreso: ProgresoEstudiante | None, curso: Curso) -> bool:
    """True si el puntero está en el penúltimo o último módulo de este curso."""
    if not progreso or progreso.completado or not progreso.modulo_actual_id:
        return False
    penultimo, ultimo = numeros_cierre_curso(curso)
    if ultimo is None:
        return False
    actual = getattr(progreso.modulo_actual, 'numero', None)
    if actual is None:
        return False
    return actual == ultimo or (penultimo is not None and actual == penultimo)


@transaction.atomic
def cerrar_curso_si_tramo_final(estudiante: Estudiante, curso: Curso) -> str:
    """
    Si el estudiante está en el penúltimo o último módulo de *este* curso,
    completa los módulos desde el actual hasta el último y marca el curso finalizado.

    No inventa módulos anteriores ni toca otros cursos.
    Returns: cerrado | omitido | ya_completo
    """
    progreso = (
        ProgresoEstudiante.objects.select_related('modulo_actual')
        .filter(estudiante=estudiante, curso=curso)
        .first()
    )
    if not progreso:
        return 'omitido'
    if progreso.completado:
        return 'ya_completo'
    if not progreso_en_tramo_cierre(progreso, curso):
        return 'omitido'

    mods = list(Modulo.objects.filter(curso=curso).order_by('numero', 'id'))
    if not mods:
        return 'omitido'
    actual_num = progreso.modulo_actual.numero
    ultimo = mods[-1]
    for modulo in mods:
        if modulo.numero < actual_num:
            continue
        ModuloCompletado.objects.get_or_create(progreso=progreso, modulo=modulo)

    progreso.modulo_actual = ultimo
    progreso.completado = True
    progreso.fecha_completado = timezone.now()
    progreso.save(update_fields=['modulo_actual', 'completado', 'fecha_completado'])
    return 'cerrado'


def _cursos_digitales_activos_por_estudiante(
    estudiante_ids: list[int],
    curso_presencial_id: int,
) -> dict[int, list[str]]:
    """Cursos con progreso incompleto distintos al curso presencial (informativo en admin)."""
    if not estudiante_ids:
        return {}
    filas = (
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=estudiante_ids,
            completado=False,
        )
        .exclude(curso_id=curso_presencial_id)
        .select_related('curso')
        .order_by('curso__orden', 'curso__nombre')
    )
    out: dict[int, list[str]] = {}
    for prog in filas:
        if prog.curso and prog.curso.activo:
            out.setdefault(prog.estudiante_id, []).append(prog.curso.nombre)
    return out


def filas_estudiantes_certificado(
    cliente,
    curso: Curso,
    *,
    grupo_id: int | None = None,
    busqueda_global: str | None = None,
    extra_estudiante_ids: set[int] | None = None,
) -> list[dict]:
    """Estudiantes del evento + búsqueda global / extras (otro cliente permitido)."""
    from django.db.models import Q

    certs = {
        c.estudiante_id: c
        for c in Certificado.objects.filter(
            curso=curso,
        ).select_related('estudiante')
    }
    ids: set[int] = set(extra_estudiante_ids or ())
    qs_local = Estudiante.objects.filter(cliente=cliente, activo=True)
    if grupo_id:
        qs_local = qs_local.filter(grupos__id=grupo_id, grupos__activo=True).distinct()
    ids.update(qs_local.values_list('pk', flat=True))

    term = (busqueda_global or '').strip()
    if len(term) >= 2:
        global_qs = Estudiante.objects.filter(activo=True).filter(
            Q(nombre__icontains=term)
            | Q(cedula__icontains=term)
            | Q(telefono__icontains=term)
        ).select_related('cliente')[:80]
        ids.update(global_qs.values_list('pk', flat=True))

    estudiantes = list(
        Estudiante.objects.filter(pk__in=ids, activo=True)
        .select_related('cliente')
        .order_by('nombre')
    )
    est_ids = [e.id for e in estudiantes]
    digitales = _cursos_digitales_activos_por_estudiante(est_ids, curso.id)
    progresos = {
        p.estudiante_id: p
        for p in ProgresoEstudiante.objects.filter(
            curso=curso, estudiante_id__in=est_ids,
        ).select_related('modulo_actual')
    }
    penultimo, ultimo = numeros_cierre_curso(curso)
    filas = []
    for est in estudiantes:
        cert = certs.get(est.id)
        otro = bool(est.cliente_id and est.cliente_id != cliente.id)
        prog = progresos.get(est.id)
        filas.append({
            'estudiante': est,
            'certificado': cert,
            'tiene_certificado': cert is not None,
            'emitido': bool(cert and cert.emitido),
            'enviado_whatsapp': bool(cert and cert.enviado_whatsapp),
            'cursos_digitales_activos': digitales.get(est.id, []),
            'otro_cliente': otro,
            'cliente_nombre': est.cliente.nombre if est.cliente else '',
            'en_tramo_cierre': progreso_en_tramo_cierre(prog, curso),
            'modulo_actual_numero': (
                prog.modulo_actual.numero if prog and prog.modulo_actual_id else None
            ),
            'curso_completado': bool(prog and prog.completado),
            'penultimo_numero': penultimo,
            'ultimo_numero': ultimo,
        })
    return filas


def buscar_estudiante_por_documento_o_telefono(
    *,
    cedula: str | None = None,
    telefono: str | None = None,
) -> Estudiante | None:
    from core.utils_telefono import normalizar_telefono

    ced = (cedula or '').strip()
    if ced:
        est = Estudiante.objects.filter(cedula=ced, activo=True).select_related('cliente').first()
        if est:
            return est
    tel = normalizar_telefono(telefono or '')
    if tel:
        return Estudiante.objects.filter(telefono=tel, activo=True).select_related('cliente').first()
    return None


def agregar_participante_certificado(
    cliente_evento: Cliente,
    *,
    nombre: str,
    cedula: str,
    telefono: str,
) -> tuple[Estudiante | None, str]:
    """
    Si ya existe (cédula/teléfono global), lo devuelve aunque sea de otro cliente.
    Si no existe, lo crea bajo cliente_evento.
    """
    from core.utils_telefono import normalizar_telefono

    nombre = (nombre or '').strip()
    cedula = (cedula or '').strip()
    telefono = normalizar_telefono(telefono or '')
    if not nombre or not cedula or not telefono:
        return None, 'datos_incompletos'

    existente = buscar_estudiante_por_documento_o_telefono(cedula=cedula, telefono=telefono)
    if existente:
        return existente, 'encontrado'

    try:
        est = Estudiante.objects.create(
            nombre=nombre,
            cedula=cedula,
            telefono=telefono,
            cliente=cliente_evento,
            activo=True,
        )
        return est, 'creado'
    except Exception:
        return None, 'error'


@transaction.atomic
def crear_certificado_presencial(
    estudiante: Estudiante,
    curso: Curso,
    *,
    calificacion: float = 100.0,
    fecha_inicio: date | None = None,
    fecha_completado: date | None = None,
    regenerar_si_existe: bool = False,
    generar_archivo: bool = True,
    plantilla: PlantillaCertificado | None = None,
    permitir_otro_cliente: bool = False,
) -> tuple[Certificado | None, str]:
    """
    Crea certificado sin exigir curso completado en WhatsApp.
    No modifica ProgresoEstudiante ni estado_chat (compatible con curso digital paralelo).
    Returns (certificado, estado): creado | existente | regenerado | error
    """
    if (
        not permitir_otro_cliente
        and estudiante.cliente_id
        and curso.cliente_id
        and estudiante.cliente_id != curso.cliente_id
    ):
        return None, 'error_cliente'

    existente = Certificado.objects.filter(estudiante=estudiante, curso=curso).first()
    if existente and not regenerar_si_existe:
        return existente, 'existente'

    hoy = timezone.now().date()
    datos = {
        'calificacion_final': calificacion,
        'fecha_inicio': fecha_inicio or hoy,
        'fecha_completado': fecha_completado or hoy,
    }

    try:
        if existente:
            for k, v in datos.items():
                setattr(existente, k, v)
            existente.emitido = False
            existente.save()
            cert = existente
            estado = 'regenerado'
        else:
            cert = Certificado.objects.create(
                estudiante=estudiante,
                curso=curso,
                **datos,
            )
            estado = 'creado'

        if generar_archivo:
            ok = generar_y_guardar_certificado(cert, plantilla=plantilla, force=bool(existente))
            if ok:
                cert.emitido = True
                cert.fecha_emision = timezone.now()
                cert.save(update_fields=['emitido', 'fecha_emision'])
            else:
                return cert, 'error_generar'

        return cert, estado
    except Exception:
        return None, 'error'


@transaction.atomic
def emitir_certificados_presenciales(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
    *,
    calificacion: float = 100.0,
    regenerar_si_existe: bool = False,
    enviar_whatsapp: bool = False,
    plantilla: PlantillaCertificado | None = None,
    permitir_otro_cliente: bool = False,
) -> dict:
    """Emite certificados a varios estudiantes del mismo curso."""
    estudiantes = Estudiante.objects.filter(pk__in=estudiante_ids, activo=True)
    if not permitir_otro_cliente:
        estudiantes = estudiantes.filter(cliente_id=curso.cliente_id)

    resumen = {
        'creados': 0,
        'existentes': 0,
        'regenerados': 0,
        'enviados': 0,
        'errores': 0,
    }

    for est in estudiantes:
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
        else:
            resumen['errores'] += 1
            continue

        if enviar_whatsapp and cert and cert.emitido:
            if enviar_certificado_whatsapp(cert):
                resumen['enviados'] += 1
            else:
                resumen['errores'] += 1

    return resumen


def info_plantilla_curso(cliente: Cliente, curso: Curso, plantilla_id: int | None = None) -> dict:
    """Texto para mostrar en admin qué plantilla se aplicará."""
    est = Estudiante.objects.filter(cliente=cliente, activo=True).first()
    plantilla, origen = resolver_plantilla_certificado(
        est,
        curso,
        plantilla_id=plantilla_id,
    )
    origen_txt = {
        'elegida_manual': 'Usted eligió esta plantilla',
        'curso_y_cliente': 'Curso + cliente (automático)',
        'curso': 'Curso (automático)',
        'cliente': 'Cliente (automático)',
        'por_defecto': 'Plantilla por defecto eki',
        'diseno_eki_default': 'Diseño eki integrado (sin plantilla en BD)',
    }
    return {
        'plantilla': plantilla,
        'origen': origen,
        'origen_txt': origen_txt.get(origen, origen),
        'opciones': plantillas_selectables_para_curso(cliente, curso),
    }


def _enviar_plantilla_twilio_cert(telefono: str, content_sid: str, variables: dict) -> dict:
    """Wrapper testeable para enviar plantilla inicial (import perezoso de Twilio)."""
    from core.enviar_plantillas import enviar_plantilla_twilio

    return enviar_plantilla_twilio(telefono, content_sid, variables=variables)


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
