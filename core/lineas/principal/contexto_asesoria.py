"""Lo que ya se sabe de la persona, en pocas líneas, para el que deriva y para los agentes.

Sin nombre, cédula ni teléfono: solo la ficha, la organización, el curso, la región
y el último asesor. Fuera del ciclo de imports: lee modelos y nada de la línea.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger(__name__)

DIAS_ULTIMO_AGENTE = 30

_NOMBRES = {
    'nat': 'Agrónomo',
    'coach': 'Coach',
    'ia_campo': 'Innovación e IA',
    'ventas': 'Ventas',
    'finanzas': 'Finanzas',
    'cafe': 'Experto en café',
}
_ETIQUETAS_LOG = {f'sandbox_{modo}': modo for modo in _NOMBRES} | {'BOT_COMERCIAL': 'nat'}


def nombre_agente(modo: str) -> str:
    return _NOMBRES.get(modo, modo)


def _lineas_ficha(telefono: str) -> list[str]:
    from core.models import FichaNegocio

    ficha = FichaNegocio.objects.filter(telefono=telefono).first()
    if ficha is None:
        return []
    lineas = []
    if ficha.dedica:
        lineas.append(f'Se dedica a: {ficha.dedica}')
    if ficha.etapa:
        lineas.append(f'Su negocio: {ficha.get_etapa_display().lower()}')
    if ficha.equipo:
        lineas.append(f'Trabaja: {ficha.get_equipo_display().lower()}')
    return lineas


def _linea_organizacion(telefono: str) -> list[str]:
    from core.conocimiento_agentes import cliente_id_para_conocimiento
    from core.models import Cliente

    cid = cliente_id_para_conocimiento(telefono)
    if not cid:
        return []
    nombre = Cliente.objects.filter(pk=cid).values_list('nombre', flat=True).first()
    return [f'Organización: {nombre}'] if nombre else []


def _lineas_estudiante(telefono: str) -> list[str]:
    from core.models import ProgresoEstudiante
    from core.utils_telefono import estudiante_por_telefono

    estudiante = estudiante_por_telefono(telefono)
    if estudiante is None:
        return []
    lineas = []
    progreso = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, completado=False)
        .select_related('curso', 'modulo_actual')
        .order_by('-fecha_inicio')
        .first()
    )
    if progreso is not None:
        modulo = progreso.modulo_actual
        if modulo is not None:
            lineas.append(f'Curso que lleva: {progreso.curso.nombre}, va en el módulo {modulo.numero}')
        else:
            lineas.append(f'Curso que lleva: {progreso.curso.nombre}')
    lugar = [x for x in (estudiante.municipio, estudiante.departamento) if (x or '').strip()]
    if not lugar and (estudiante.region or '').strip():
        lugar = [estudiante.region]
    if lugar:
        lineas.append(f"Región: {', '.join(x.strip() for x in lugar)}")
    return lineas


def ultimo_agente(telefono: str) -> tuple[str, str] | None:
    """(modo, tema) del último asesor con el que habló en los últimos 30 días."""
    from core.conocimiento_agentes import _sin_datos_personales
    from core.models import WhatsappLog

    desde = timezone.now() - timedelta(days=DIAS_ULTIMO_AGENTE)
    fila = (
        WhatsappLog.objects.filter(
            telefono=telefono, fecha__gte=desde, tipo='INCOMING', agente_usado__in=list(_ETIQUETAS_LOG),
        )
        .exclude(mensaje__isnull=True)
        .exclude(mensaje='')
        .order_by('-fecha')
        .values_list('agente_usado', 'mensaje')
        .first()
    )
    if fila is None:
        return None
    tema = ' '.join(_sin_datos_personales(fila[1]).split())
    if len(tema) > 120:
        tema = tema[:117] + '...'
    return _ETIQUETAS_LOG[fila[0]], tema


def _lineas_entrada(telefono: str) -> list[str]:
    """Nombre, cómo está y el lugar que ella dijo. Sin municipio del registro."""
    from core.models import FichaNegocio
    from core.utils_telefono import estudiante_por_telefono

    lineas = []
    nombre = ''
    estudiante = estudiante_por_telefono(telefono)
    if estudiante is not None:
        nombre = (estudiante.nombre or '').strip()
        if nombre.lower() == 'usuario':
            nombre = ''
    ficha = FichaNegocio.objects.filter(telefono=telefono).first()
    if not nombre and ficha is not None and (ficha.trato or '').strip():
        nombre = ficha.trato.strip()
    if nombre:
        lineas.append(f'Nombre: {nombre.split()[0]}')
    if ficha is None:
        return lineas
    if (ficha.como_esta or '').strip():
        lineas.append(f'Hoy está: {ficha.como_esta.strip()}')
    if (ficha.lugar or '').strip():
        lineas.append(f'Es de: {ficha.lugar.strip()}')
    return lineas


def contexto_persona(telefono: str) -> str:
    """Líneas cortas con lo que se sabe. Vacío si no se sabe nada."""
    tel = (telefono or '').strip()
    if not tel:
        return ''
    lineas = _lineas_ficha(tel) + _linea_organizacion(tel) + _lineas_estudiante(tel)
    if getattr(settings, 'EKI_ASESORIA_ENTRADA', False):
        lineas = [linea for linea in lineas if not linea.startswith('Región:')]
        lineas = _lineas_entrada(tel) + lineas
    ultimo = ultimo_agente(tel)
    if ultimo is not None:
        modo, tema = ultimo
        lineas.append(f'Último asesor: {nombre_agente(modo)}. Le preguntó: «{tema}»')
    return '\n'.join(f'- {linea}' for linea in lineas)


def bloque_perfil(telefono: str) -> str:
    """Para el prompt de cualquier agente. Vacío con el flag apagado o si no se sabe nada."""
    if not getattr(settings, 'EKI_ASESORIA_CONTEXTO', False) and not getattr(
        settings, 'EKI_ASESORIA_ENTRADA', False,
    ):
        return ''
    try:
        contexto = contexto_persona(telefono)
    except DatabaseError:
        logger.exception('asesoria_perfil_fail')
        return ''
    if not contexto:
        return ''
    return (
        'LO QUE SABEMOS DE LA PERSONA (úselo para adaptar la respuesta a su caso; '
        'no lo recite ni le diga que ya lo sabe):\n'
        f'{contexto}'
    )
