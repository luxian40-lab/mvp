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
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_certificados import Certificado, PlantillaCertificado


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
        ).select_related('cliente')[:40]
        ids.update(global_qs.values_list('pk', flat=True))

    estudiantes = list(
        Estudiante.objects.filter(pk__in=ids, activo=True)
        .select_related('cliente')
        .order_by('nombre')
    )
    digitales = _cursos_digitales_activos_por_estudiante(
        [e.id for e in estudiantes],
        curso.id,
    )
    filas = []
    for est in estudiantes:
        cert = certs.get(est.id)
        otro = bool(est.cliente_id and est.cliente_id != cliente.id)
        filas.append({
            'estudiante': est,
            'certificado': cert,
            'tiene_certificado': cert is not None,
            'emitido': bool(cert and cert.emitido),
            'enviado_whatsapp': bool(cert and cert.enviado_whatsapp),
            'cursos_digitales_activos': digitales.get(est.id, []),
            'otro_cliente': otro,
            'cliente_nombre': est.cliente.nombre if est.cliente else '',
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


@transaction.atomic
def enviar_whatsapp_certificados_existentes(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
) -> dict:
    """Reenvía por WhatsApp certificados ya emitidos (sin regenerar PDF)."""
    enviados = errores = omitidos = 0
    for cert in Certificado.objects.filter(
        curso=curso,
        estudiante_id__in=estudiante_ids,
        estudiante__cliente_id=curso.cliente_id,
        emitido=True,
    ).select_related('estudiante'):
        if enviar_certificado_whatsapp(cert):
            enviados += 1
        else:
            errores += 1
    total_sel = len(set(estudiante_ids))
    omitidos = total_sel - enviados - errores
    return {'enviados': enviados, 'errores': errores, 'omitidos': omitidos}


def enviar_certificados_seleccion(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
    *,
    mensaje_previo: str | None = None,
    emitir_certificado: bool = True,
    enviar_whatsapp_certificado: bool = True,
    calificacion: float = 100.0,
    regenerar_si_existe: bool = False,
    plantilla: PlantillaCertificado | None = None,
    permitir_otro_cliente: bool = True,
) -> dict:
    """
    Flujo tipo campaña + certificado para los marcados.
    No toca ProgresoEstudiante ni onboarding.
    """
    from core.utils import enviar_whatsapp_twilio

    estudiantes = Estudiante.objects.filter(pk__in=estudiante_ids, activo=True)
    if not permitir_otro_cliente:
        estudiantes = estudiantes.filter(cliente_id=curso.cliente_id)

    resumen = {
        'mensajes_previos': 0,
        'creados': 0,
        'existentes': 0,
        'regenerados': 0,
        'certificados_enviados': 0,
        'omitidos': 0,
        'errores': 0,
    }

    texto_previo = (mensaje_previo or '').strip()
    for est in estudiantes:
        try:
            if texto_previo:
                cuerpo = texto_previo.replace('{nombre}', est.nombre or 'Estudiante')
                cuerpo = cuerpo.replace('{cedula}', est.cedula or '')
                cuerpo = cuerpo.replace('{curso}', curso.nombre or '')
                ok_prev = enviar_whatsapp_twilio(telefono=est.telefono, texto=cuerpo)
                if ok_prev.get('success'):
                    resumen['mensajes_previos'] += 1
                else:
                    resumen['errores'] += 1
                    continue

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

            if enviar_whatsapp_certificado and cert and cert.emitido:
                if enviar_certificado_whatsapp(cert):
                    resumen['certificados_enviados'] += 1
                else:
                    resumen['errores'] += 1
            elif enviar_whatsapp_certificado and emitir_certificado:
                resumen['errores'] += 1
        except Exception:
            resumen['errores'] += 1

    return resumen
