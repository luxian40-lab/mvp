"""Reglas de un módulo y sus pasos que el modelo necesita (contenido mínimo, evaluación, video).

Sin imports de negocio: los modelos se cargan dentro de cada función.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

if TYPE_CHECKING:
    from core.models import Modulo, PasoModulo


def cuenta_microcontenidos_modulo(modulo: Optional[Modulo]) -> int:
    """Microcontenidos guardados en BD (cualquier estado activo/inactivo)."""
    if not modulo or not getattr(modulo, 'pk', None):
        return 0
    from core.models import PasoModulo

    return PasoModulo.objects.filter(modulo=modulo).count()


def cuenta_secciones_modulo(modulo: Optional[Modulo]) -> int:
    if not modulo or not getattr(modulo, 'pk', None):
        return 0
    from core.models import SeccionModulo

    return SeccionModulo.objects.filter(modulo=modulo).count()


def cuenta_secciones_en_post(data) -> int:
    """Bloques en el POST (Estructura) aún no persistidos."""
    if not data:
        return 0
    for prefix in ('secciones', 'seccionmodulo_set'):
        raw_total = data.get(f'{prefix}-TOTAL_FORMS')
        if raw_total is None:
            continue
        try:
            total = int(raw_total)
        except (TypeError, ValueError):
            continue
        n = 0
        for i in range(total):
            if data.get(f'{prefix}-{i}-DELETE'):
                continue
            if data.get(f'{prefix}-{i}-id') or (data.get(f'{prefix}-{i}-titulo') or '').strip():
                n += 1
        return n
    return 0


def _paso_form_cuenta_como_microcontenido(cleaned_data: dict) -> bool:
    if not cleaned_data or cleaned_data.get('DELETE'):
        return False
    return bool(cleaned_data.get('seccion'))


def _paso_form_marcado_borrar(form) -> bool:
    cd = getattr(form, 'cleaned_data', None) or {}
    if cd.get('DELETE'):
        return True
    data = getattr(form, 'data', None)
    if data is None:
        return False
    return bool(data.get(f'{form.prefix}-DELETE'))


def cuenta_microcontenidos_desde_formset(pasos_formset) -> int:
    """Cuenta pasos válidos en el POST; si el form no limpió, cae al instance guardado."""
    if not pasos_formset:
        return 0
    n = 0
    for form in pasos_formset.forms:
        if _paso_form_marcado_borrar(form):
            continue
        cd = getattr(form, 'cleaned_data', None)
        if cd and _paso_form_cuenta_como_microcontenido(cd):
            n += 1
            continue
        # Form con error / vacío: no borrar lo ya persistido con sección.
        inst = getattr(form, 'instance', None)
        if inst is not None and getattr(inst, 'pk', None) and getattr(inst, 'seccion_id', None):
            n += 1
    return n


def ids_pasos_marcados_borrar(pasos_formset) -> set[int]:
    if not pasos_formset:
        return set()
    out: set[int] = set()
    for form in pasos_formset.forms:
        if not _paso_form_marcado_borrar(form):
            continue
        pk = getattr(getattr(form, 'instance', None), 'pk', None)
        if pk:
            out.add(int(pk))
    return out


def cuenta_microcontenidos_efectivos(modulo: Optional[Modulo], *, pasos_formset=None) -> int:
    """
    Microcontenidos que quedan tras guardar: POST (formset) + fallback BD
    (excluye los marcados para borrar). Evita exigir Modulo.contenido cuando
    ya hay pasos guardados pero el formset no aportó cleaned_data útil.
    """
    if pasos_formset is not None:
        n_form = cuenta_microcontenidos_desde_formset(pasos_formset)
        if n_form > 0:
            return n_form
        if not modulo or not getattr(modulo, 'pk', None):
            return 0
        from core.models import PasoModulo

        borrados = ids_pasos_marcados_borrar(pasos_formset)
        qs = PasoModulo.objects.filter(modulo=modulo)
        if borrados:
            qs = qs.exclude(pk__in=borrados)
        return qs.count()
    return cuenta_microcontenidos_modulo(modulo)


def _post_tiene_clase_simple(data, files=None) -> bool:
    """Pestaña Clase del admin: texto, archivo o URL sustituyen contenido legacy."""
    if data:
        if (data.get('clase_texto') or '').strip():
            return True
        if (data.get('clase_url') or '').strip():
            return True
    if files and files.get('clase_archivo'):
        return True
    return False


def modulo_requiere_contenido_texto(
    modulo: Optional[Modulo],
    *,
    pasos_formset=None,
    tiene_clase_simple: bool = False,
    data=None,
) -> bool:
    """
    True solo si no hay NINGUNA fuente de material:
    - microcontenidos (BD o formset)
    - bloques/secciones (BD o POST de Estructura)
    - pestaña Clase (texto/archivo/URL)
    Evita el choque «contenido obligatorio» al guardar Estructura/Materiales/Clase.
    """
    if tiene_clase_simple or _post_tiene_clase_simple(data):
        return False
    if cuenta_microcontenidos_efectivos(modulo, pasos_formset=pasos_formset) > 0:
        return False
    if cuenta_secciones_modulo(modulo) > 0:
        return False
    if cuenta_secciones_en_post(data) > 0:
        return False
    return True


def validar_contenido_modulo(
    contenido: str,
    modulo: Optional[Modulo],
    *,
    pasos_formset=None,
    tiene_clase_simple: bool = False,
    data=None,
) -> None:
    from django.core.exceptions import ValidationError

    if modulo_requiere_contenido_texto(
        modulo,
        pasos_formset=pasos_formset,
        tiene_clase_simple=tiene_clase_simple,
        data=data,
    ):
        if not (contenido or '').strip():
            raise ValidationError(
                'Falta material: use la pestaña Clase (texto/archivo), '
                'o cree un bloque en Estructura y un material, '
                'o complete el texto legacy en «Más opciones».'
            )


def _letra_correcta_eval_opciones(paso: PasoModulo) -> str:
    """Letra correcta A–D: prioriza el campo admin, luego opciones_json; no exige dict de textos."""
    rc = (getattr(paso, 'respuesta_correcta', None) or '').strip().upper()[:1]
    if rc in ('A', 'B', 'C', 'D'):
        return rc
    data = paso.opciones_json or {}
    if isinstance(data, dict):
        c = data.get('correcta')
        if c is None:
            c = data.get('respuesta_correcta')
        if c is not None:
            letra = str(c).strip().upper()[:1]
            if letra in ('A', 'B', 'C', 'D'):
                return letra
    return ''


def _opciones_dict(paso: PasoModulo) -> dict[str, str]:
    """Textos A–D: campos del admin y, si faltan letras, claves en opciones_json (cualquier tipo)."""
    out: dict[str, str] = {}
    for letter in ('A', 'B', 'C', 'D'):
        raw = getattr(paso, f'eval_opcion_{letter.lower()}', None) or ''
        v = str(raw).strip()
        if v:
            out[letter] = v
    data = paso.opciones_json or {}
    if isinstance(data, dict):
        for letter in ('A', 'B', 'C', 'D'):
            if letter in out:
                continue
            val = data.get(letter)
            if val is None or not str(val).strip():
                val = data.get(letter.lower())
            if val is not None and str(val).strip():
                out[letter] = str(val).strip()
        for alt_key, letter in (
            ('opcion_a', 'A'),
            ('opcion_b', 'B'),
            ('opcion_c', 'C'),
            ('opcion_d', 'D'),
        ):
            if letter in out:
                continue
            val = data.get(alt_key)
            if val is not None and str(val).strip():
                out[letter] = str(val).strip()
    return out


def paso_contenido_con_mc_como_eval(paso: PasoModulo) -> bool:
    """Contenido configurado como texto pero con A–D + correcta (tipo mal elegido en admin)."""
    from core.models import PasoModulo

    if paso.tipo != PasoModulo.TIPO_CONTENIDO:
        return False
    opts = _opciones_dict(paso)
    letra = _letra_correcta_eval_opciones(paso)
    return len(opts) >= 2 and letra in opts


_VIDEO_EXT = ('.mp4', '.m4v', '.mov', '.webm', '.3gp')


_HOSTS_REDIRECT = (
    'youtube.com',
    'youtu.be',
    'youtube-nocookie.com',
    'vimeo.com',
)


def es_video_rastreable(url: str) -> bool:
    """True solo para video. Imagen, PDF y audio siguen como adjunto de WhatsApp."""
    raw = (url or '').strip()
    if not raw:
        return False
    path = raw.split('?', 1)[0].lower()
    if any(path.endswith(ext) for ext in _VIDEO_EXT):
        return True
    host = (urlparse(raw).hostname or '').lower()
    if host.endswith(_HOSTS_REDIRECT) or host in _HOSTS_REDIRECT:
        return True
    if '/videos/' in path:
        return True
    return False
