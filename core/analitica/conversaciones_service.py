"""Datos del inbox de conversaciones WhatsApp (admin y portal)."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.utils import timezone

from core.models import Cliente, EnvioLog, Estudiante, WhatsappLog
from core.utils_telefono import normalizar_telefono, variantes_telefono

MSG_LIMIT = 400
PAGE_SIZE = 80


def _fecha_aware(fecha):
    if not fecha:
        return timezone.now()
    if timezone.is_naive(fecha):
        return timezone.make_aware(fecha)
    return fecha


def _ts_orden(fecha):
    if not fecha:
        return 0
    return _fecha_aware(fecha).timestamp()


def _estudiantes_por_telefono() -> dict[str, Estudiante]:
    est_por_tel: dict[str, Estudiante] = {}
    for est in Estudiante.objects.select_related('cliente').exclude(telefono=''):
        key = normalizar_telefono(est.telefono)
        if key:
            est_por_tel[key] = est
    return est_por_tel


def _construir_contactos(est_por_tel: dict[str, Estudiante], cliente_filtro_id: int | None) -> list[dict]:
    from django.db.models import Count, Max

    contactos_por_tel: dict[str, dict] = {}
    logs_agg = (
        WhatsappLog.objects.values('telefono')
        .annotate(ultima_fecha=Max('fecha'), total=Count('id'))
        .order_by('-ultima_fecha')
    )
    for row in logs_agg:
        tel_raw = row['telefono'] or ''
        tel_norm = normalizar_telefono(tel_raw)
        if not tel_norm:
            continue
        ultimo = (
            WhatsappLog.objects.filter(telefono=tel_raw)
            .order_by('-fecha')
            .values('mensaje', 'tipo', 'agente_usado')
            .first()
        )
        est = est_por_tel.get(tel_norm)
        for v in variantes_telefono(tel_norm):
            if v in est_por_tel and est is None:
                est = est_por_tel[v]
        cliente = getattr(est, 'cliente', None) if est else None
        contactos_por_tel[tel_norm] = {
            'telefono': tel_norm,
            'telefono_display': tel_raw or tel_norm,
            'estudiante_id': est.id if est else None,
            'nombre': (est.nombre if est else tel_norm),
            'cliente_id': cliente.id if cliente else None,
            'cliente_nombre': (cliente.nombre if cliente else 'Sin organización'),
            'ultima_fecha': row['ultima_fecha'],
            'ultimo_mensaje': (ultimo or {}).get('mensaje') or '',
            'ultimo_tipo': (ultimo or {}).get('tipo') or '',
            'agente': (ultimo or {}).get('agente_usado') or '',
            'total_mensajes': row['total'],
        }

    from django.db.models import Count as Cnt

    for est in Estudiante.objects.select_related('cliente').annotate(
        n_envios=Cnt('enviolog', distinct=True),
    ).filter(n_envios__gt=0):
        tel_norm = normalizar_telefono(est.telefono)
        if not tel_norm:
            continue
        ultimo_envio = (
            EnvioLog.objects.filter(estudiante=est)
            .select_related('campana')
            .order_by('-fecha_envio')
            .first()
        )
        if not ultimo_envio:
            continue
        prev = contactos_por_tel.get(tel_norm)
        fecha_env = ultimo_envio.fecha_envio
        if prev and prev.get('ultima_fecha'):
            if _ts_orden(fecha_env) <= _ts_orden(prev['ultima_fecha']):
                prev['total_mensajes'] = prev.get('total_mensajes', 0) + est.n_envios
                continue
        cliente = est.cliente
        contactos_por_tel[tel_norm] = {
            'telefono': tel_norm,
            'telefono_display': est.telefono,
            'estudiante_id': est.id,
            'nombre': est.nombre,
            'cliente_id': cliente.id if cliente else None,
            'cliente_nombre': (cliente.nombre if cliente else 'Sin organización'),
            'ultima_fecha': fecha_env,
            'ultimo_mensaje': f"Campaña: {ultimo_envio.campana.nombre}",
            'ultimo_tipo': 'SENT',
            'agente': '',
            'total_mensajes': est.n_envios,
        }

    contactos = list(contactos_por_tel.values())
    if cliente_filtro_id:
        contactos = [c for c in contactos if c.get('cliente_id') == cliente_filtro_id]

    contactos.sort(
        key=lambda c: (
            (c.get('cliente_nombre') or '').lower(),
            -_ts_orden(c.get('ultima_fecha')),
        ),
    )
    return contactos


def _agrupar_por_cliente(contactos: list[dict]) -> list[dict]:
    grupos_dict: dict[str, list] = {}
    for c in contactos:
        grupos_dict.setdefault(c['cliente_nombre'], []).append(c)
    return [
        {'cliente_nombre': nombre, 'contactos': items}
        for nombre, items in sorted(grupos_dict.items(), key=lambda x: x[0].lower())
    ]


def _mensajes_contacto(estudiante_seleccionado, telefono_param: str, est_por_tel: dict) -> list[dict]:
    tel_norm = normalizar_telefono(telefono_param)
    vars_tel = variantes_telefono(telefono_param)
    if estudiante_seleccionado is None:
        estudiante_seleccionado = est_por_tel.get(tel_norm)

    lista_mensajes = []
    wa_qs = (
        WhatsappLog.objects.filter(telefono__in=vars_tel)
        .order_by('-fecha')[:MSG_LIMIT]
    )
    for msg in reversed(list(wa_qs)):
        fecha = _fecha_aware(msg.fecha)
        texto = msg.mensaje or ''
        if msg.es_audio and msg.audio_transcripcion:
            texto = msg.audio_transcripcion
        elif msg.es_audio:
            texto = texto or '(mensaje de audio)'
        lista_mensajes.append({
            'mensaje': texto,
            'fecha': fecha,
            'estado': msg.estado or '',
            'tipo': 'recibido' if msg.tipo == 'INCOMING' else 'enviado',
            'agente': msg.agente_usado or '',
            'es_audio': bool(msg.es_audio),
        })

    if estudiante_seleccionado:
        envio_qs = (
            EnvioLog.objects.filter(estudiante=estudiante_seleccionado)
            .select_related('campana', 'campana__plantilla')
            .order_by('-fecha_envio')[:MSG_LIMIT]
        )
        for envio in reversed(list(envio_qs)):
            fecha = _fecha_aware(envio.fecha_envio)
            campana = envio.campana
            plantilla = getattr(campana, 'plantilla', None) if campana else None
            if plantilla and getattr(plantilla, 'cuerpo_mensaje', None):
                cuerpo = plantilla.cuerpo_mensaje.replace(
                    '{nombre}', estudiante_seleccionado.nombre or '',
                )
            else:
                cuerpo = f"Campaña: {campana.nombre if campana else 'sin nombre'}"
            lista_mensajes.append({
                'mensaje': cuerpo,
                'fecha': fecha,
                'estado': envio.estado or '',
                'tipo': 'enviado',
                'agente': 'Campaña',
                'es_audio': False,
            })

    lista_mensajes.sort(key=lambda x: _fecha_aware(x['fecha']).timestamp())
    return lista_mensajes


def construir_contexto_inbox(
    *,
    cliente_filtro_id: int | None = None,
    estudiante_id: int | None = None,
    telefono: str | None = None,
    page: int = 1,
    busqueda: str | None = None,
    org_fijo: Cliente | None = None,
    mostrar_filtro_clientes: bool = True,
) -> dict:
    """Contexto compartido para templates de conversaciones."""
    if org_fijo is not None:
        cliente_filtro_id = org_fijo.pk
        mostrar_filtro_clientes = False

    est_por_tel = _estudiantes_por_telefono()
    contactos = _construir_contactos(est_por_tel, cliente_filtro_id)
    q_raw = (busqueda or '').strip()
    if q_raw:
        q_low = q_raw.lower()
        contactos = [
            c for c in contactos
            if q_low in (c.get('nombre') or '').lower()
            or q_low in (c.get('telefono') or '')
            or q_low in (c.get('telefono_display') or '')
            or q_low in (c.get('cliente_nombre') or '').lower()
        ]
    grupos_cliente = _agrupar_por_cliente(contactos)

    estudiante_seleccionado = None
    contacto_seleccionado = None
    mensajes = []
    page_obj = None

    if estudiante_id:
        try:
            estudiante_seleccionado = Estudiante.objects.select_related('cliente').get(id=estudiante_id)
            if org_fijo and estudiante_seleccionado.cliente_id != org_fijo.pk:
                estudiante_seleccionado = None
            else:
                telefono = estudiante_seleccionado.telefono
        except Estudiante.DoesNotExist:
            estudiante_seleccionado = None

    if telefono:
        tel_norm = normalizar_telefono(telefono)
        if estudiante_seleccionado is None:
            estudiante_seleccionado = est_por_tel.get(tel_norm)
            if org_fijo and estudiante_seleccionado and estudiante_seleccionado.cliente_id != org_fijo.pk:
                estudiante_seleccionado = None

        contacto_map = {c['telefono']: c for c in contactos}
        contacto_seleccionado = contacto_map.get(tel_norm) or {
            'telefono': tel_norm,
            'telefono_display': telefono,
            'nombre': (
                estudiante_seleccionado.nombre if estudiante_seleccionado else tel_norm
            ),
        }

        lista = _mensajes_contacto(estudiante_seleccionado, telefono, est_por_tel)
        paginator = Paginator(lista, PAGE_SIZE)
        page_obj = paginator.get_page(page)
        mensajes = page_obj.object_list

    clientes_qs = Cliente.objects.filter(activo=True).order_by('nombre')

    return {
        'grupos_cliente': grupos_cliente,
        'total_contactos': len(contactos),
        'clientes': clientes_qs,
        'cliente_filtro': cliente_filtro_id,
        'mostrar_filtro_clientes': mostrar_filtro_clientes,
        'org_nombre': org_fijo.nombre if org_fijo else '',
        'estudiante_seleccionado': estudiante_seleccionado,
        'contacto_seleccionado': contacto_seleccionado,
        'mensajes': mensajes,
        'page_obj': page_obj,
        'busqueda': q_raw,
    }
