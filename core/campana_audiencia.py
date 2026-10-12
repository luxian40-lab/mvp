"""Audiencia, embudo y textos de Campaña Meta.

El envío a Graph sigue en meta_waba. Aquí se decide quién entra y cómo se muestra.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from core.models_campana_meta import EnvioCampanaMeta, PlantillaMeta, variables_en

ORIGENES = (
    ('nombre', 'Nombre'),
    ('organizacion', 'Organización'),
    ('curso', 'Curso'),
    ('fijo', 'Texto fijo'),
)
SI_FALTA = (
    ('respaldo', 'Usar un texto de respaldo'),
    ('excluir', 'Excluir a la persona'),
)
_DEFECTO_ORIGEN = {1: 'nombre', 2: 'organizacion', 3: 'curso'}
_NO_REINTENTAR = ('ENVIADO', 'ERROR', 'OMITIDO', 'INCIERTO')
_FALLIDOS = ('ERROR', 'FALLIDO', 'ERROR_REINTENTABLE')

# Textos de los códigos que el proyecto ya trata. Fecha de la lista de códigos: 2026-10-03.
MOTIVO_CODIGO = {
    '130429': 'Meta limitó el ritmo de envío. Se puede reintentar.',
    '131056': 'Hay demasiados mensajes al mismo tiempo. Se puede reintentar.',
    '4': 'Meta pidió esperar un momento. Se puede reintentar.',
    '80008': 'Meta pidió esperar un momento. Se puede reintentar.',
    '613': 'Meta pidió esperar un momento. Se puede reintentar.',
    '131047': 'Fuera de la ventana de 24 horas.',
    '131026': 'Ese número no puede recibir el mensaje.',
    '131048': 'Meta limitó esta plantilla por calidad.',
    '131049': 'Meta no entregó el mensaje por la calidad de la plantilla.',
    '131052': 'El archivo del mensaje no se pudo cargar.',
    '131053': 'El archivo del mensaje no es válido.',
    '190': 'La sesión con Meta no es válida.',
}


class FaltaDato(ValueError):
    """La regla de la variable pide excluir a la persona."""


def dias_de(campana) -> int:
    bruto = getattr(campana, 'dias_repeticion', None)
    if bruto is None:
        bruto = getattr(settings, 'EKI_CAMPANA_META_DIAS_REPETICION', 14)
    try:
        return max(0, int(bruto))
    except (TypeError, ValueError):
        return 14


def digitos(telefono: str) -> str:
    return ''.join(c for c in str(telefono or '') if c.isdigit())


def telefono_valido(telefono: str) -> bool:
    cantidad = len(digitos(telefono))
    return 10 <= cantidad <= 15


def ultimos_4(telefono: str) -> str:
    numero = digitos(telefono)
    if len(numero) < 4:
        return 'sin teléfono'
    return numero[-4:]


def etiqueta_persona(estudiante) -> str:
    if getattr(estudiante, 'cliente_id', None):
        org = (getattr(estudiante.cliente, 'nombre', None) or '').strip() or 'Sin organización'
    else:
        org = 'Sin organización'
    nombre = (getattr(estudiante, 'nombre', None) or '').strip() or 'Sin nombre'
    return f'{nombre} · {org} · {ultimos_4(estudiante.telefono)}'


def etiqueta_grupo(grupo) -> str:
    return f'{grupo.nombre} · {grupo.estudiantes.filter(activo=True).count()} personas'


def _curso_nombre(estudiante) -> str:
    progresos = getattr(estudiante, 'progresos', None)
    if progresos is None:
        return ''
    progreso = progresos.select_related('curso').order_by('-id').first()
    if progreso is None or not progreso.curso_id:
        return ''
    return (progreso.curso.nombre or '').strip()


def resolver_token(token: str, estudiante) -> str:
    """Sustituye un token del mapeo. nombre y telefono conservan el comportamiento anterior."""
    clave = (token or '').strip()
    if clave.endswith('?excluir'):
        valor = resolver_token(clave[: -len('?excluir')], estudiante)
        if not valor:
            raise FaltaDato(clave)
        return valor
    marca = '?respaldo:'
    if marca in clave:
        base, respaldo = clave.split(marca, 1)
        valor = resolver_token(base, estudiante)
        return valor or respaldo
    if clave.startswith('fijo:'):
        return clave[5:]
    if clave == 'nombre':
        return (getattr(estudiante, 'nombre', None) or 'Estudiante').strip() or 'Estudiante'
    if clave == 'telefono':
        return str(getattr(estudiante, 'telefono', None) or '').strip()
    if clave in ('organizacion', 'organizacion.nombre'):
        cliente = getattr(estudiante, 'cliente', None)
        if cliente is None:
            return ''
        return (getattr(cliente, 'nombre', None) or '').strip()
    if clave in ('curso', 'curso.nombre'):
        return _curso_nombre(estudiante)
    return clave


def token_de_regla(regla: dict) -> str:
    origen = (regla or {}).get('origen') or 'fijo'
    if origen == 'fijo':
        return 'fijo:' + str((regla or {}).get('texto') or '')
    if origen == 'nombre' and (regla or {}).get('si_falta') != 'excluir':
        return 'nombre'
    if (regla or {}).get('si_falta') == 'excluir':
        return f'{origen}?excluir'
    respaldo = str((regla or {}).get('respaldo') or '')
    if respaldo:
        return f'{origen}?respaldo:{respaldo}'
    return origen


def _regla_vacia(numero: int) -> dict:
    return {
        'origen': _DEFECTO_ORIGEN.get(numero, 'fijo'),
        'si_falta': 'respaldo',
        'respaldo': '',
        'texto': '',
    }


def _regla_desde_token(token: str, numero: int) -> dict:
    regla = _regla_vacia(numero)
    clave = (token or '').strip()
    if clave.endswith('?excluir'):
        regla['si_falta'] = 'excluir'
        clave = clave[: -len('?excluir')]
    elif '?respaldo:' in clave:
        base, respaldo = clave.split('?respaldo:', 1)
        regla['si_falta'] = 'respaldo'
        regla['respaldo'] = respaldo
        clave = base
    if clave.startswith('fijo:'):
        regla['origen'] = 'fijo'
        regla['texto'] = clave[5:]
        return regla
    if clave in ('nombre', 'organizacion', 'organizacion.nombre', 'curso', 'curso.nombre', 'telefono'):
        regla['origen'] = {
            'organizacion.nombre': 'organizacion',
            'curso.nombre': 'curso',
            'telefono': 'fijo',
        }.get(clave, clave if clave != 'telefono' else 'fijo')
        if clave == 'telefono':
            regla['texto'] = ''
            regla['origen'] = 'fijo'
        return regla
    if clave in ('nombre', 'organizacion', 'curso'):
        regla['origen'] = clave
        return regla
    regla['origen'] = 'fijo'
    regla['texto'] = clave
    return regla


def numeros_plantilla(plantilla: PlantillaMeta | None) -> list[int]:
    if plantilla is None:
        return []
    numeros = set(variables_en(plantilla.cuerpo))
    numeros.update(variables_en(plantilla.header_texto))
    numeros.update(variables_en(plantilla.boton_1_url))
    numeros.update(variables_en(plantilla.boton_2_url))
    return sorted(numeros)


def reglas_efectivas(campana) -> dict[str, dict]:
    """Reglas por {{n}}. Si no hay reglas guardadas, se leen del mapeo que ya envía."""
    plantilla = getattr(campana, 'plantilla', None)
    numeros = numeros_plantilla(plantilla)
    guardadas = campana.reglas_variables if isinstance(getattr(campana, 'reglas_variables', None), dict) else {}
    if not guardadas:
        partes = [p.strip() for p in (campana.mapeo_body or '').split('|') if p.strip()]
        for indice, token in enumerate(partes, start=1):
            guardadas.setdefault(str(indice), _regla_desde_token(token, indice))
    salida = {}
    for numero in numeros:
        previa = guardadas.get(str(numero)) if isinstance(guardadas.get(str(numero)), dict) else None
        base = _regla_vacia(numero)
        if previa:
            origen = previa.get('origen') or base['origen']
            if origen not in {clave for clave, _ in ORIGENES}:
                origen = 'fijo'
            si_falta = previa.get('si_falta') or 'respaldo'
            if si_falta not in {clave for clave, _ in SI_FALTA}:
                si_falta = 'respaldo'
            base.update({
                'origen': origen,
                'si_falta': si_falta,
                'respaldo': str(previa.get('respaldo') or ''),
                'texto': str(previa.get('texto') or ''),
            })
        salida[str(numero)] = base
    return salida


def aplicar_mapeo(campana) -> None:
    """Escribe mapeo_body, mapeo_header y mapeo_boton desde las reglas. No envía."""
    plantilla = campana.plantilla
    reglas = reglas_efectivas(campana)
    campana.reglas_variables = reglas

    def serie(numeros: list[int]) -> str:
        return '|'.join(token_de_regla(reglas.get(str(n)) or _regla_vacia(n)) for n in numeros)

    cuerpo = sorted(set(variables_en(plantilla.cuerpo)))
    header = sorted(set(variables_en(plantilla.header_texto)))
    botones = sorted(set(variables_en(plantilla.boton_1_url) + variables_en(plantilla.boton_2_url)))
    if cuerpo:
        campana.mapeo_body = serie(cuerpo)
    if header and not (campana.mapeo_header or '').strip():
        campana.mapeo_header = serie(header)
    if botones and not (campana.mapeo_boton or '').strip():
        campana.mapeo_boton = serie(botones)


def _ids_con_repeticion(campana) -> list[int]:
    """Ids activos, con repetición si la persona está en varios grupos o también a mano."""
    from core.models import Estudiante

    if _usa_audiencia_nueva(campana):
        ids = list(campana.destinatarios.filter(activo=True).values_list('id', flat=True))
        grupos = list(campana.grupos.values_list('id', flat=True))
        if campana.grupo_id and campana.grupo_id not in grupos:
            grupos.append(campana.grupo_id)
        if grupos:
            ids.extend(
                Estudiante.objects.filter(grupos__in=grupos, activo=True).values_list('id', flat=True)
            )
        return ids
    if campana.grupo_id:
        return list(campana.grupo.estudiantes.filter(activo=True).values_list('id', flat=True))
    return list(campana.destinatarios.filter(activo=True).values_list('id', flat=True))


def _usa_audiencia_nueva(campana) -> bool:
    if not hasattr(campana, 'grupos'):
        return False
    if campana.pk and campana.grupos.exists():
        return True
    return False


def _recientes(campana) -> set[int]:
    if not campana.plantilla_id:
        return set()
    limite = timezone.now() - timedelta(days=dias_de(campana))
    return set(
        EnvioCampanaMeta.objects.filter(
            campana__plantilla_id=campana.plantilla_id,
            estado='ENVIADO',
            fecha__gte=limite,
        ).values_list('estudiante_id', flat=True)
    )


def _falta_variable(estudiante, reglas: dict) -> bool:
    for regla in reglas.values():
        if regla.get('si_falta') != 'excluir':
            continue
        try:
            resolver_token(token_de_regla(regla), estudiante)
        except FaltaDato:
            return True
    return False


def resumir_audiencia(campana) -> dict:
    from core.models import Estudiante

    crudos = _ids_con_repeticion(campana)
    unicos = []
    vistos = set()
    for pk in crudos:
        if pk in vistos:
            continue
        vistos.add(pk)
        unicos.append(pk)
    personas = {
        est.pk: est
        for est in Estudiante.objects.filter(pk__in=unicos).select_related('cliente')
    }
    reglas = reglas_efectivas(campana) if campana.plantilla_id else {}
    recientes = _recientes(campana)
    optout = recientes_n = sin_whatsapp = sin_variable = 0
    reciben = []
    telefonos = set()
    sin_organizacion = sin_curso = sin_nombre = 0
    for pk in unicos:
        est = personas.get(pk)
        if est is None:
            continue
        if est.wa_optout_fecha:
            optout += 1
            continue
        if not telefono_valido(est.telefono):
            sin_whatsapp += 1
            continue
        numero = digitos(est.telefono)
        if numero in telefonos:
            sin_whatsapp += 1
            continue
        if pk in recientes:
            recientes_n += 1
            continue
        if not est.cliente_id:
            sin_organizacion += 1
        if not (est.nombre or '').strip():
            sin_nombre += 1
        if not _curso_nombre(est):
            sin_curso += 1
        if reglas and _falta_variable(est, reglas):
            sin_variable += 1
            continue
        telefonos.add(numero)
        reciben.append(pk)
    return {
        'suma': len(crudos),
        'repetidas': len(crudos) - len(unicos),
        'optout': optout,
        'recientes': recientes_n,
        'sin_whatsapp': sin_whatsapp,
        'sin_variable': sin_variable,
        'reciben_ids': reciben,
        'reciben': len(reciben),
        'sin_organizacion': sin_organizacion,
        'sin_curso': sin_curso,
        'sin_nombre': sin_nombre,
        'dias': dias_de(campana),
        'ejemplo_id': reciben[0] if reciben else None,
    }


def personas_que_reciben(campana):
    from core.models import Estudiante

    ids = resumir_audiencia(campana)['reciben_ids']
    if not ids:
        return []
    orden = {pk: n for n, pk in enumerate(ids)}
    personas = list(Estudiante.objects.filter(pk__in=ids).select_related('cliente'))
    personas.sort(key=lambda est: orden.get(est.pk, 0))
    return personas


def avisos_compatibilidad(campana, resumen: dict | None = None) -> list[dict]:
    resumen = resumen or resumir_audiencia(campana)
    if not campana.plantilla_id or resumen['reciben'] == 0 and resumen['suma'] == 0:
        return []
    reglas = reglas_efectivas(campana)
    avisos = []
    etiquetas = {
        'organizacion': ('sin organización', resumen['sin_organizacion']),
        'curso': ('sin curso', resumen['sin_curso']),
        'nombre': ('sin nombre', resumen['sin_nombre']),
    }
    for numero, regla in reglas.items():
        par = etiquetas.get(regla.get('origen'))
        if not par or par[1] <= 0:
            continue
        if regla.get('si_falta') == 'excluir':
            accion = 'quedan fuera de la campaña'
        else:
            texto = regla.get('respaldo') or ('Estudiante' if regla.get('origen') == 'nombre' else 'el texto de respaldo')
            accion = f'se usa «{texto}»'
        avisos.append({
            'texto': f'{par[1]} personas {par[0]}. En {{{{{numero}}}}} {accion}.',
            'numero': numero,
        })
    return avisos


def sugerir_plantilla(campana, resumen: dict | None = None) -> PlantillaMeta | None:
    resumen = resumen or resumir_audiencia(campana)
    if not campana.plantilla_id or resumen['sin_organizacion'] <= 0:
        return None
    reglas = reglas_efectivas(campana)
    if not any(regla.get('origen') == 'organizacion' for regla in reglas.values()):
        return None
    actual = len(variables_en(campana.plantilla.cuerpo))
    candidatas = (
        PlantillaMeta.objects.filter(activa=True, estado='APPROVED')
        .exclude(pk=campana.plantilla_id)
        .order_by('id')
    )
    mejor = None
    for candidata in candidatas:
        numeros = set(variables_en(candidata.cuerpo))
        if 2 in numeros and actual >= 2:
            continue
        if len(numeros) >= actual and actual:
            continue
        mejor = candidata
        break
    return mejor


def sustituir(texto: str, estudiante, reglas: dict) -> str:
    salida = texto or ''
    for numero in sorted(variables_en(salida)):
        regla = reglas.get(str(numero)) or _regla_vacia(numero)
        try:
            valor = resolver_token(token_de_regla(regla), estudiante)
        except FaltaDato:
            valor = ''
        salida = salida.replace(f'{{{{{numero}}}}}', valor)
    return salida


def vista_previa(campana, estudiante=None) -> dict:
    plantilla = getattr(campana, 'plantilla', None)
    if plantilla is None:
        return {'cuerpo': '', 'header': '', 'footer': '', 'botones': [], 'persona': ''}
    reglas = reglas_efectivas(campana)
    if estudiante is None and campana.pk:
        ejemplo = resumir_audiencia(campana)['ejemplo_id']
        if ejemplo:
            from core.models import Estudiante

            estudiante = Estudiante.objects.filter(pk=ejemplo).select_related('cliente').first()
    if estudiante is None:
        cuerpo = plantilla.cuerpo or ''
        header = plantilla.header_texto or ''
        persona = ''
    else:
        cuerpo = sustituir(plantilla.cuerpo, estudiante, reglas)
        header = sustituir(plantilla.header_texto, estudiante, reglas)
        persona = etiqueta_persona(estudiante)
    botones = []
    for n in (1, 2):
        texto = (getattr(plantilla, f'boton_{n}_texto') or '').strip()
        if texto:
            botones.append(texto)
    return {
        'cuerpo': cuerpo,
        'header': header,
        'footer': plantilla.footer or '',
        'botones': botones,
        'persona': persona,
    }


def nombre_linea(campana) -> str:
    from core.plantilla_meta_editor import lineas_disponibles

    actual = (campana.phone_number_id or '').strip()
    for valor, etiqueta in lineas_disponibles():
        if actual and actual == valor:
            return etiqueta
    if not actual:
        return 'Línea principal'
    return 'Línea 2' if len(lineas_disponibles()) > 1 else 'Línea principal'


def estado_campana(campana, ahora=None) -> tuple[str, str]:
    ahora = ahora or timezone.now()
    plantilla = getattr(campana, 'plantilla', None)
    aprobada = bool(plantilla and plantilla.estado == 'APPROVED')
    if campana.pausa_motivo == 'plantilla_no_aprobada' or (
        not campana.ejecutada and campana.fecha_programada and not aprobada
    ):
        return 'errores', 'Con errores'
    fallidos = _n_fallidos(campana)
    if campana.ejecutada and fallidos:
        return 'errores', 'Con errores'
    if campana.ejecutada:
        return 'enviada', 'Enviada'
    if _enviando(campana):
        return 'enviando', 'Enviando'
    if campana.fecha_programada and not campana.ejecutada and aprobada:
        return 'programada', 'Programada'
    return 'borrador', 'Borrador'


def _n_fallidos(campana) -> int:
    anotado = getattr(campana, 'n_fallidos', None)
    if anotado is not None:
        return int(anotado)
    if not campana.pk:
        return 0
    return campana.envios.filter(estado__in=_FALLIDOS).count()


def _enviando(campana) -> bool:
    if not campana.pk or campana.ejecutada:
        return False
    return campana.envios.filter(estado__in=('ENVIANDO', 'PENDIENTE')).exists()


def embudo(campana) -> dict:
    if not campana.pk:
        return _embudo_vacio()
    filas = list(campana.envios.values_list('estado', 'estado_entrega'))
    enviados = sum(1 for estado, _ in filas if estado == 'ENVIADO')
    fallidos = sum(1 for estado, _ in filas if estado in _FALLIDOS)
    con_dato = any((entrega or '').strip() for _, entrega in filas)
    if enviados and not con_dato:
        entregados = 'Sin dato'
        leidos = 'Sin dato'
    else:
        entregados = sum(1 for _, entrega in filas if entrega in ('delivered', 'read'))
        leidos = sum(1 for _, entrega in filas if entrega == 'read')
    return {
        'enviados': enviados,
        'entregados': entregados,
        'leidos': leidos,
        'respondieron': 'Sin dato',
        'fallidos': fallidos,
    }


def _embudo_vacio() -> dict:
    return {
        'enviados': 0,
        'entregados': 'Sin dato',
        'leidos': 'Sin dato',
        'respondieron': 'Sin dato',
        'fallidos': 0,
    }


def texto_embudo(datos: dict) -> str:
    return (
        f"Enviados {datos['enviados']}"
        f" · Entregados {datos['entregados']}"
        f" · Leídos {datos['leidos']}"
        f" · Respondieron {datos['respondieron']}"
    )


def con_conteos(qs):
    if 'n_fallidos' in getattr(qs.query, 'annotations', {}):
        return qs
    from django.db.models import Count

    return qs.annotate(
        n_fallidos=Count('envios', filter=Q(envios__estado__in=_FALLIDOS), distinct=True),
    )


def filtrar_estado(qs, clave: str, ahora=None):
    ahora = ahora or timezone.now()
    qs = con_conteos(qs)
    if not clave:
        return qs
    error_plantilla = Q(pausa_motivo='plantilla_no_aprobada') | Q(
        ejecutada=False,
        fecha_programada__isnull=False,
        plantilla__estado__in=[
            'BORRADOR', 'PENDING', 'REJECTED', 'PAUSED', 'DISABLED', 'IN_APPEAL', 'ERROR', 'NO_EXISTE',
        ],
    )
    con_fallos = Q(ejecutada=True, n_fallidos__gt=0)
    if clave == 'errores':
        return qs.filter(error_plantilla | con_fallos)
    if clave == 'enviadas':
        return qs.filter(ejecutada=True, n_fallidos=0).exclude(error_plantilla)
    if clave == 'programadas':
        return qs.filter(
            ejecutada=False,
            fecha_programada__isnull=False,
            plantilla__estado='APPROVED',
        ).exclude(pausa_motivo='plantilla_no_aprobada')
    if clave == 'borradores':
        return qs.filter(ejecutada=False, fecha_programada__isnull=True).exclude(
            pausa_motivo='plantilla_no_aprobada',
        )
    return qs


def conteos_estado(qs) -> dict[str, int]:
    base = qs.all()
    return {
        '': base.count(),
        'borradores': filtrar_estado(base, 'borradores').count(),
        'programadas': filtrar_estado(base, 'programadas').count(),
        'enviadas': filtrar_estado(base, 'enviadas').count(),
        'errores': filtrar_estado(base, 'errores').count(),
    }


def motivo_fallo(envio) -> str:
    codigo = (envio.error_codigo or '').strip()
    if codigo and codigo in MOTIVO_CODIGO:
        return MOTIVO_CODIGO[codigo]
    if codigo:
        return f'Sin dato (código {codigo})'
    texto = (envio.respuesta or '').strip()
    if texto:
        return texto[:180]
    return 'Sin dato'


def puede_reintentar(envio) -> bool:
    if envio.estado == 'ERROR_REINTENTABLE':
        return True
    codigos = {str(c) for c in (getattr(settings, 'META_CODIGOS_REINTENTABLES', None) or [])}
    return (envio.error_codigo or '') in codigos and envio.estado in _FALLIDOS


def debe_omitir_reintento(previo) -> bool:
    if previo is None:
        return False
    if previo.estado in _NO_REINTENTAR:
        return True
    if previo.estado == 'ENVIADO':
        return True
    if previo.estado == 'FALLIDO' and not puede_reintentar(previo):
        return True
    if previo.estado == 'ERROR' and not puede_reintentar(previo):
        return True
    return False


def numeros_de_prueba() -> list[str]:
    bruto = getattr(settings, 'EKI_CAMPANA_META_PRUEBA_NUMEROS', None) or ['573026480629']
    if isinstance(bruto, str):
        bruto = [p.strip() for p in bruto.split(',') if p.strip()]
    return [digitos(p) for p in bruto if digitos(p)]


def poner_en_inicio_de_flujo(estudiante) -> None:
    """Deja a la persona al inicio del habeas de la línea Meta.

    El recordatorio no llama esto: su respuesta sigue en el modo que ya tenía.
    """
    from core.models import SandboxCanalSesion
    from core.sandbox_menu import MODO_MENU
    from core.utils_telefono import normalizar_e164_co

    telefono = normalizar_e164_co(getattr(estudiante, 'telefono', '') or '')
    if telefono:
        sesion, _ = SandboxCanalSesion.objects.get_or_create(
            telefono=telefono,
            defaults={'modo': MODO_MENU, 'habeas_aceptado': False},
        )
        sesion.modo = MODO_MENU
        sesion.habeas_aceptado = False
        sesion.save(update_fields=['modo', 'habeas_aceptado', 'actualizado_en'])
    if not getattr(estudiante, 'pk', None):
        return
    estudiante.estado_chat = 'ESPERANDO_HABEAS_DATA'
    estudiante.acepto_terminos = False
    estudiante.estado_onboarding = 'nuevo'
    estudiante.save(update_fields=['estado_chat', 'acepto_terminos', 'estado_onboarding'])


def numero_de_prueba_permitido(telefono: str) -> bool:
    return digitos(telefono) in set(numeros_de_prueba())


def marcar_programadas_sin_aprobacion(ahora=None) -> int:
    """Si la plantilla ya no está aprobada, la campaña queda en error y no se encola."""
    from core.models_campana_meta import CampanaMeta

    ahora = ahora or timezone.now()
    qs = (
        CampanaMeta.objects.filter(
            fecha_programada__isnull=False,
            fecha_programada__lte=ahora,
            ejecutada=False,
            pausada=False,
        )
        .exclude(plantilla__estado='APPROVED')
        .select_related('plantilla')
    )
    n = 0
    for campana in qs:
        campana.pausada = True
        campana.pausa_motivo = 'plantilla_no_aprobada'
        campana.save(update_fields=['pausada', 'pausa_motivo'])
        n += 1
    return n


def texto_confirmacion(campana, resumen: dict | None = None) -> str:
    resumen = resumen or resumir_audiencia(campana)
    plantilla = campana.plantilla.nombre_interno if campana.plantilla_id else 'Sin plantilla'
    return (
        f'Se enviará a {resumen["reciben"]} personas, '
        f'desde {nombre_linea(campana)}, '
        f'con la plantilla {plantilla}. '
        f'Repetidas: {resumen["repetidas"]}. '
        f'Pidieron no recibir más: {resumen["optout"]}. '
        f'Recibieron esta plantilla hace menos de {resumen["dias"]} días: {resumen["recientes"]}. '
        f'Sin WhatsApp válido: {resumen["sin_whatsapp"]}. '
        f'Sin el dato de una variable: {resumen["sin_variable"]}.'
    )
