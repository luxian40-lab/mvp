"""Qué empresa, qué cursos y qué agentes corresponden a la línea de este turno.

Vacío no cambia el comportamiento: sin phone id en el cliente, el carrusel
sigue siendo el general. Sin lista de agentes, siguen los cinco.
"""
from __future__ import annotations

AGENTES = (
    ('nat', 'Agrónomo', 'Experto en café'),
    ('coach', 'Coach', 'Motivación y metas diarias'),
    ('profe', 'Innovación e IA', 'Mejor apropiación tecnológica'),
    ('ventas', 'Ventas', 'Aumenta tus ingresos'),
    ('finanzas', 'Finanzas', 'Educación financiera a tu alcance'),
)

_MODO = {
    'nat': 'nat',
    'agronomo': 'nat',
    'agrónomo': 'nat',
    'cafe': 'nat',
    'café': 'nat',
    'coach': 'coach',
    'profe': 'ia_campo',
    'ia': 'ia_campo',
    'ia_campo': 'ia_campo',
    'ventas': 'ventas',
    'finanzas': 'finanzas',
}

_FILA_MODO = {
    'nat': 'nat',
    'coach': 'coach',
    'profe': 'ia_campo',
    'ventas': 'ventas',
    'finanzas': 'finanzas',
}


def _claves(texto: str) -> set[str]:
    salida = set()
    for parte in (texto or '').replace(';', ',').split(','):
        modo = _MODO.get(parte.strip().lower())
        if modo:
            salida.add(modo)
    return salida


def cliente_de_la_linea(phone_id: str | None = None):
    """La empresa dueña del phone number id de este turno. None si nadie lo reclamó."""
    if phone_id is None:
        from core.sandbox_canal import phone_id_de_salida

        phone_id = phone_id_de_salida()
    buscado = str(phone_id or '').strip()
    if not buscado:
        return None
    from core.lineas.meta import linea_por_phone_id
    from core.models import Cliente

    linea = linea_por_phone_id(buscado)
    if linea is not None and linea.cliente_id:
        cliente = Cliente.objects.filter(pk=linea.cliente_id, activo=True).first()
        if cliente is not None:
            return cliente
    return Cliente.objects.filter(phone_id_meta=buscado, activo=True).order_by('id').first()


def cliente_de_la_oferta(telefono: str | None):
    """Empresa de la línea, o la del estudiante si la línea no es de nadie."""
    cliente = cliente_de_la_linea()
    if cliente is not None or not telefono:
        return cliente
    from core.models import Estudiante
    from core.nati import normalizar_telefono_whatsapp

    est = Estudiante.objects.filter(telefono=normalizar_telefono_whatsapp(telefono)).first()
    if est is None or not est.cliente_id:
        return None
    return est.cliente


def modos_permitidos(telefono: str) -> set[str] | None:
    """None = los cinco. Conjunto = solo esos. Vacío = esta línea no abre agentes."""
    from core.nati import normalizar_telefono_whatsapp

    cliente = cliente_de_la_oferta(telefono)
    if cliente is None or not (cliente.agentes_linea or '').strip():
        permitidos = None
    else:
        permitidos = _claves(cliente.agentes_linea)
    if cliente is None:
        return permitidos
    from core.models import Estudiante

    tel = normalizar_telefono_whatsapp(telefono)
    est = Estudiante.objects.filter(telefono=tel).first()
    if est is None:
        return permitidos
    apagados = set()
    grupos = est.grupos.filter(activo=True, cliente=cliente)
    for grupo in grupos:
        apagados |= _claves(getattr(grupo, 'agentes_apagados', ''))
    if not apagados:
        return permitidos
    base = permitidos if permitidos is not None else {modo for _, modo in _FILA_MODO.items()}
    return base - apagados


def agente_permitido(telefono: str, modo: str) -> bool:
    clave = _MODO.get((modo or '').strip().lower(), '')
    if not clave:
        return True
    permitidos = modos_permitidos(telefono)
    if permitidos is None:
        return True
    return clave in permitidos


def filas_agentes(telefono: str) -> list[tuple[str, str, str]]:
    permitidos = modos_permitidos(telefono)
    if permitidos is None:
        return list(AGENTES)
    return [fila for fila in AGENTES if _FILA_MODO[fila[0]] in permitidos]


def cursos_de_la_linea(telefono: str | None):
    """Cursos que esta persona puede ver. None = catálogo general de eki.

    La línea 2 (modo Twilio) no usa carrusel: el curso entra por campaña
    o inscripción; esta función no la recorta.
    Si la empresa marcó cursos, esos. Si no marcó nada y la línea es suya,
    los cursos activos de la empresa. El grupo, si tiene cursos, recorta esa lista.
    """
    from core.lineas.variante import perfil_de
    from core.models import Curso, Estudiante
    from core.nati import normalizar_telefono_whatsapp

    if not perfil_de().varios_cursos:
        return None

    cliente_linea = cliente_de_la_linea()
    est = None
    if telefono:
        est = Estudiante.objects.filter(telefono=normalizar_telefono_whatsapp(telefono)).first()
    cliente = cliente_linea or (est.cliente if est is not None and est.cliente_id else None)
    if cliente is None:
        return None
    seleccion = cliente.cursos_whatsapp.filter(activo=True)
    if seleccion.exists():
        base = seleccion
    elif cliente_linea is not None:
        base = Curso.objects.filter(cliente=cliente, activo=True)
    else:
        return None
    orden = ('orden', 'nombre', 'id')
    if est is None:
        return base.order_by(*orden)
    de_grupos = base.filter(
        grupos__estudiantes=est, grupos__activo=True, grupos__cliente=cliente,
    ).distinct()
    if de_grupos.exists():
        return de_grupos.order_by(*orden)
    return base.order_by(*orden)
