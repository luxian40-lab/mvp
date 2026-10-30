"""FAQ institucional por organización + contacto oficial (PQRS)."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from django.utils.text import slugify

_STOP = frozenset({
    'a', 'al', 'de', 'del', 'la', 'las', 'el', 'los', 'un', 'una', 'unos', 'unas',
    'y', 'o', 'en', 'por', 'para', 'con', 'que', 'qué', 'como', 'cómo', 'mi', 'su',
    'me', 'se', 'es', 'son', 'hay', 'the', 'of', 'and',
})

_PATRON_ORG = re.compile(
    r'\b('
    r'bono|n[oó]mina|pago|pag(?:an|o|ar)|convenio|contrato|empresa|organizaci[oó]n|'
    r'recursos?\s+humanos|rr\.?\s*hh\.?|\brh\b|jefe|supervisor|coordinador\s+de\s+la\s+empresa|'
    r'afiliaci[oó]n|eps|caja\s+de\s+compensaci[oó]n|auxilio|subsidio|beneficio|'
    r'horario\s+laboral|dotaci[oó]n|carnet|carnetizaci[oó]n|sede\s+de\s+la\s+empresa'
    r')\b',
    re.I,
)


def _norm(texto: str) -> str:
    t = unicodedata.normalize('NFKD', texto or '')
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', t.lower()).strip()


def _tokens(texto: str) -> set[str]:
    words = re.findall(r'[a-z0-9áéíóúñü]{3,}', _norm(texto), flags=re.I)
    out = set()
    for w in words:
        w2 = _norm(w)
        if w2 in _STOP or len(w2) < 3:
            continue
        out.add(w2)
        # slugify ayuda a unificar
        s = slugify(w2)
        if s and len(s) >= 3:
            out.add(s)
    return out


def parece_consulta_organizacion(mensaje: str) -> bool:
    return bool(_PATRON_ORG.search(mensaje or ''))


def texto_contacto_organizacion(cliente) -> str:
    if not cliente:
        return (
            'Por favor comuníquese con el contacto de su organización o escriba a '
            'comunidad.educativa@eki.com.co.'
        )
    bloque = (getattr(cliente, 'contacto_soporte_texto', None) or '').strip()
    if bloque:
        return (
            f'Esa consulta corresponde a su organización ({cliente.nombre}), no al contenido del curso.\n\n'
            f'{bloque}\n\n'
            'También puede esperar respuesta de su coordinador por este canal; '
            'su solicitud quedó registrada.'
        )
    return (
        f'Esa consulta corresponde a su organización ({cliente.nombre}), no al contenido del curso.\n\n'
        'Comuníquese con su coordinador o facilitador de la organización. '
        'Su solicitud quedó registrada para que le respondan.'
    )


def buscar_faq_organizacion(cliente, mensaje: str):
    """Devuelve (faq, score) o (None, 0). Match léxico simple por org."""
    if not cliente or not (mensaje or '').strip():
        return None, 0.0

    from core.models import FaqOrganizacion

    faqs = list(
        FaqOrganizacion.objects.filter(cliente=cliente, activo=True).order_by('orden', 'id')[:40]
    )
    if not faqs:
        return None, 0.0

    msg_tok = _tokens(mensaje)
    if not msg_tok:
        return None, 0.0

    mejor = None
    mejor_score = 0.0
    for faq in faqs:
        base = _tokens(faq.pregunta) | _tokens(faq.palabras_clave)
        if not base:
            continue
        inter = msg_tok & base
        if not inter:
            continue
        score = len(inter) / max(len(base), 1)
        # bonus si casi todas las palabras clave de la FAQ están
        if faq.palabras_clave.strip():
            kw = _tokens(faq.palabras_clave)
            if kw and kw <= msg_tok:
                score += 0.35
        if score > mejor_score:
            mejor_score = score
            mejor = faq

    # Umbral: al menos 1 token fuerte o score decente
    if mejor and (mejor_score >= 0.28 or len(msg_tok & _tokens(mejor.pregunta)) >= 2):
        return mejor, mejor_score
    return None, 0.0


def listar_faqs_para_contexto(cliente, limite: int = 12) -> str:
    if not cliente:
        return ''
    from core.models import FaqOrganizacion

    faqs = FaqOrganizacion.objects.filter(cliente=cliente, activo=True).order_by('orden', 'id')[:limite]
    if not faqs:
        return ''
    lineas = ['FAQ DE LA ORGANIZACIÓN (use solo si aplica; no invente):']
    for f in faqs:
        lineas.append(f'- P: {f.pregunta}')
        lineas.append(f'  R: {(f.respuesta or "")[:280]}')
    return '\n'.join(lineas)
