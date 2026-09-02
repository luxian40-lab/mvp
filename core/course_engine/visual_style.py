"""Perfiles visuales Course Engine — documental vs ilustración."""
from __future__ import annotations

import re

PERFIL_DOCUMENTAL = 'documental'

_KEYFRAME_AGRO = (
    'Fotografía documental profesional, cámara DSLR, luz natural, '
    'productor rural colombiano en su finca, texturas reales, '
    'profundidad de campo suave, estilo reportaje agrícola, '
    'NO ilustración, NO CGI, NO arte digital, sin texto ni marcas de agua.'
)

_KEYFRAME_FINANZAS = (
    'Fotografía documental profesional, luz natural en espacio de trabajo rural: '
    'mesa con cuaderno de gastos, calculadora, facturas o celular con app de finanzas, '
    'emprendedor joven revisando números con socio o asesor, bodega u oficina de finca, '
    'estilo reportaje educativo empresarial, '
    'NO campo de cultivo, NO cosecha, NO ilustración, NO CGI, '
    'sin texto legible en pantalla, sin marcas de agua.'
)

_KEYFRAME_GENERICO = (
    'Fotografía documental profesional Colombia rural, luz natural, '
    'escena coherente con la lección educativa, personas reales trabajando, '
    'NO ilustración, NO CGI, sin texto ni marcas de agua.'
)

_MOTION_BASE = (
    'Movimiento muy sutil de cámara tipo documental: slow dolly lateral suave, '
    'misma escena del keyframe, luz natural consistente, sin morphing fantástico, '
    'sin objetos flotantes, ambiente educativo profesional.'
)

_FINANZAS_KW = re.compile(
    r'\b(finanz|rentabil|gesti[oó]n\s+financ|dinero|costo|margen|precio|venta|gananc|'
    r'presupuesto|contab|emprend|negocio|utilidad|ingreso|gasto|socio|morosidad|'
    r'cobranza|factur|auditor[ií]a|inversi[oó]n|flujo\s+de\s+efectivo|cuentas)\w*',
    re.I,
)

_AGRO_KW = re.compile(
    r'\b(café|caficultor|tomate|maíz|ganado|leche|miel|panela|aguacate|'
    r'cosecha|siembra|fumig|fertiliz|plaga|hect[aá]rea|cultivo|finca\s+de)\w*',
    re.I,
)


def inferir_categoria_visual(texto: str) -> str:
    t = (texto or '').strip()
    if _FINANZAS_KW.search(t):
        return 'finanzas'
    if _AGRO_KW.search(t):
        return 'agro'
    return 'otro'


def _plantilla_por_categoria(categoria: str) -> str:
    if categoria == 'finanzas':
        return _KEYFRAME_FINANZAS
    if categoria == 'agro':
        return _KEYFRAME_AGRO
    return _KEYFRAME_GENERICO


def prompt_keyframe_documental(
    *,
    tema: str = '',
    escena_visual: str = '',
    categoria_visual: str = '',
) -> str:
    escena = (escena_visual or '').strip()
    if escena:
        return (
            f'Fotografía documental profesional, Colombia. {escena} '
            'NO ilustración, NO CGI, NO render 3D, sin texto legible, sin marcas de agua.'
        )
    tema = (tema or 'Lección educativa rural').strip()
    cat = (categoria_visual or inferir_categoria_visual(tema)).strip().lower()
    base = _plantilla_por_categoria(cat)
    return f'{base} Tema educativo (la imagen DEBE ilustrar esto): {tema[:500]}.'


def prompt_runway_documental(
    *,
    tema: str = '',
    escena_visual: str = '',
    categoria_visual: str = '',
) -> str:
    escena = (escena_visual or '').strip()
    if escena:
        return (
            f'{_MOTION_BASE} Mantener exactamente esta escena: {escena}. '
            'Sin cambiar a campo o cosecha si no aparece en la escena.'
        )
    tema = (tema or 'lección educativa').strip()
    cat = (categoria_visual or inferir_categoria_visual(tema)).strip().lower()
    if cat == 'finanzas':
        escena_hint = 'gestión financiera y costos en emprendimiento rural'
    else:
        escena_hint = tema[:300]
    return f'{_MOTION_BASE} La escena visual debe corresponder a: {escena_hint}.'


def sufijo_imagen_documental() -> str:
    return (
        ' Fotografía real documental, NO ilustración digital, NO render 3D, '
        'NO estilo cartoon, granos de película natural, Colombia.'
    )
